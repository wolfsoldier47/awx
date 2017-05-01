import re
import sys
from pyparsing import (
    infixNotation,
    opAssoc,
    Optional,
    Literal,
    CharsNotIn,
)

from django.db import models


__all__ = ['DynamicFilter']

unicode_spaces = [unichr(c) for c in xrange(sys.maxunicode) if unichr(c).isspace()]
unicode_spaces_other = unicode_spaces + [u'(', u')', u'=', u'"']


def string_to_type(t):
    if t == u'true':
        return True
    elif t == u'false':
        return False

    if re.search('^[-+]?[0-9]+$',t):
        return int(t)

    if re.search('^[-+]?[0-9]+\.[0-9]+$',t):
        return float(t)

    return t


class DynamicFilter(object):
    SEARCHABLE_RELATIONSHIP = 'ansible_facts'

    class BoolOperand(object):
        def __init__(self, t):
            kwargs = dict()
            k, v = self._extract_key_value(t)
            k, v = self._json_path_to_contains(k, v)
            kwargs[k] = v
            self.result = models.Q(**kwargs)

        def strip_quotes_traditional_logic(self, v):
            if type(v) is unicode and v.startswith('"') and v.endswith('"'):
                return v[1:-1]
            return v

        def strip_quotes_json_logic(self, v):
            if type(v) is unicode and v.startswith('"') and v.endswith('"') and v != u'"null"':
                return v[1:-1]
            return v

        '''
        TODO: We should be able to express this in the grammar and let
              pyparsing do the heavy lifting.
        TODO: separate django filter requests from our custom json filter
              request so we don't process the key any. This could be
              accomplished using a whitelist or introspecting the
              relationship refered to to see if it's a jsonb type.
        '''
        def _json_path_to_contains(self, k, v):
            if not k.startswith(DynamicFilter.SEARCHABLE_RELATIONSHIP):
                v = self.strip_quotes_traditional_logic(v)
                return (k, v)

            # Strip off leading relationship key
            if k.startswith(DynamicFilter.SEARCHABLE_RELATIONSHIP + '__'):
                strip_len = len(DynamicFilter.SEARCHABLE_RELATIONSHIP) + 2
            else:
                strip_len = len(DynamicFilter.SEARCHABLE_RELATIONSHIP)
            k = k[strip_len:]

            pieces = k.split(u'__')

            assembled_k = u'%s__contains' % (DynamicFilter.SEARCHABLE_RELATIONSHIP)
            assembled_v = None

            last_v = None
            last_kv = None

            for i, piece in enumerate(pieces):
                new_kv = dict()
                if piece.endswith(u'[]'):
                    new_v = []
                    new_kv[piece[0:-2]] = new_v
                else:
                    new_v = dict()
                    new_kv[piece] = new_v

                if last_kv is None:
                    assembled_v = new_kv
                elif type(last_v) is list:
                    last_v.append(new_kv)
                elif type(last_v) is dict:
                    last_kv[last_kv.keys()[0]] = new_kv

                last_v = new_v
                last_kv = new_kv

            v = self.strip_quotes_json_logic(v)

            if type(last_v) is list:
                last_v.append(v)
            elif type(last_v) is dict:
                last_kv[last_kv.keys()[0]] = v

            return (assembled_k, assembled_v)

        def _extract_key_value(self, t):
            t_len = len(t)

            k = None
            v = None

            # key
            # "something"=
            v_offset = 2
            if t_len >= 2 and t[0] == "\"" and t[2] == "\"":
                k = t[1]
                v_offset = 4
            # something=
            else:
                k = t[0]

            # value
            # ="something"
            if t_len > (v_offset + 2) and t[v_offset] == "\"" and t[v_offset + 2] == "\"":
                v = u'"' + unicode(t[v_offset + 1]) + u'"'
                #v = t[v_offset + 1]
            # empty ""
            elif t_len > (v_offset + 1):
                v = u""
            # no ""
            else:
                v = string_to_type(t[v_offset])

            return (k, v)


    class BoolBinOp(object):
        def __init__(self, t):
            self.result = None
            i = 2
            while i < len(t[0]):
                if not self.result:
                    self.result = t[0][0].result
                right = t[0][i].result
                self.result = self.execute_logic(self.result, right)
                i += 2


    class BoolAnd(BoolBinOp):
        def execute_logic(self, left, right):
            return left & right


    class BoolOr(BoolBinOp):
        def execute_logic(self, left, right):
            return left | right


    class BoolNot(object):
        def __init__(self, t):
            self.right = t[0][1].result

            self.result = self.execute_logic(self.right)

        def execute_logic(self, right):
            return ~right


    @classmethod
    def query_from_string(cls, filter_string):

        '''
        TODO:
        * handle values with " via: a.b.c.d="hello\"world"
        * handle keys with " via: a.\"b.c="yeah"
        * handle key with __ in it
        '''
        filter_string_raw = filter_string
        filter_string = unicode(filter_string)

        atom = CharsNotIn(unicode_spaces_other)
        atom_inside_quotes = CharsNotIn(u'"')
        atom_quoted = Literal('"') + Optional(atom_inside_quotes) + Literal('"')
        EQUAL = Literal('=')

        grammar = ((atom_quoted | atom) + EQUAL + Optional((atom_quoted | atom)))
        grammar.setParseAction(cls.BoolOperand)

        boolExpr = infixNotation(grammar, [
            ("not", 1, opAssoc.RIGHT, cls.BoolNot),
            ("and", 2, opAssoc.LEFT, cls.BoolAnd),
            ("or",  2, opAssoc.LEFT, cls.BoolOr),
        ])

        try:
            res = boolExpr.parseString('(' + filter_string + ')')
        #except ParseException as e:
        except Exception:
            raise RuntimeError(u"Invalid query %s" % filter_string_raw)

        if len(res) > 0:
            return res[0].result

        raise RuntimeError("Parsing the filter_string %s went terribly wrong" % filter_string)
