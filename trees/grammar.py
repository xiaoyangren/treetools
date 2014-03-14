""" 
treetools: Tools for transforming treebank trees.

This module provides functions and classes for grammar extraction

Author: Wolfgang Maier <maierw@hhu.de>
"""
from __future__ import print_function
import argparse
import io
import sys
from . import trees, treeinput, misc


# PMCFG constants
PRAGMA = ":"
RULE = ":"
RULEARROW = "<-"
LINEARIZATION = "="
SEQUENCE = "->"


def pmcfg(grammar, dest, dest_enc, **opts):
    """Write grammar in PMCFG format.
    """
    lindef_to_id = {}
    id_to_lindef = {}
    func_id = 1
    lindef_id = 1
    with io.open("%s.pmcfg" % dest, 'w', encoding=dest_enc) as dest_stream:
        for func in grammar:
            for lin in grammar[func]:
                count = sum(grammar[func][lin].values())
                dest_stream.write(u" fun%d %s %s %s %s\n" 
                                  % (func_id, RULE, func[0], RULEARROW, 
                                     ' '.join(func[1:])))
                dest_stream.write(u" fun%d %s" % (func_id, LINEARIZATION))
                for lindef in lin:
                    if not lindef in lindef_to_id:
                        lindef_to_id[lindef] = lindef_id
                        id_to_lindef[lindef_id] = lindef
                        lindef_id += 1
                    dest_stream.write(u" s%s" % lindef_to_id[lindef])
                dest_stream.write(u"\n")
                dest_stream.write(u" fun%d %d\n" % (func_id, count))
                func_id += 1
        for lindef_id in sorted(id_to_lindef, key=int):
            dest_stream.write(u" s%s %s %s\n" 
                              % (lindef_id, SEQUENCE, id_to_lindef[lindef_id]))


def extract(tree, grammar):
    """Extract a PMCFG. We remember "bare" CFG productions, together with 
    possible linearizations, together with vertical contexts from the tree
    (for later markovization). So far no extraction of rules from pre-terminal
    level.
    """
    for subtree in trees.preorder(tree):
        if trees.has_children(subtree):
            # map terminal indices to the positions of the rhs elements
            # by which they are covered, furthermore build bare rule
            term_map = {}
            func = [subtree['label']]
            for i, child in enumerate(trees.children(subtree)):
                func.append(child['label'])
                for terminal in trees.terminals(child):
                    term_map[terminal['num']] = i
            func = tuple(func)
            # build linearization
            lin = []
            # position within rhs element
            rhs_argpos = [0] * (len(func) - 1)
            # one lhs argument per block in the tree
            for block in trees.terminal_blocks(subtree):
                lin.append([])
                # loop through terminals
                for terminal in block:
                    rhs_pos = term_map[terminal['num']]
                    # append the number of the rhs element which covers
                    # the current terminal if nothing has been appended yet
                    # or if the current element is different from the last one
                    # appended
                    if len(lin[-1]) == 0 or not lin[-1][-1][0] == rhs_pos:
                        lin[-1].append((rhs_pos, rhs_argpos[rhs_pos]))
                        rhs_argpos[rhs_pos] += 1
                # make the argument a tuple
                lin[-1] = tuple(lin[-1])
            lin = tuple(lin)
            # vertical context for markovization
            vert = tuple([dom['label'] for dom in trees.dominance(subtree)])
            if not func in grammar:
                grammar[func] = {}
            if not lin in grammar[func]:
                grammar[func][lin] =  {} 
            if not vert in grammar[func][lin]:
                grammar[func][lin][vert] = 0
            grammar[func][lin][vert] += 1
    return grammar


def add_parser(subparsers):
    """Add an argument parser to the subparsers of treetools.py.
    """
    parser = subparsers.add_parser('grammar', 
                                   usage='%(prog)s src dest [options] ', 
                                   formatter_class=argparse. 
                                   RawDescriptionHelpFormatter,
                                   description='grammar extraction from' \
                                   ' treebank trees')
    parser.add_argument('src', help='input file')
    parser.add_argument('dest', help='prefix of output files')
    parser.add_argument('--src-format', metavar='FMT',
                        choices=[fun.__name__ 
                                 for fun in treeinput.INPUT_FORMATS],
                        help='input format (default: %(default)s)', 
                        default='export')
    parser.add_argument('--src-enc', metavar='ENCODING', 
                        help='input encoding (default: %(default)s)', 
                        default='utf-8')
    parser.add_argument('--src-opts', nargs='+', metavar='O',
                        help='space separated list of options O for reading ' \
                            'input of the form key:value ' \
                            '(default: %(default)s)', 
                        default=[])
    parser.add_argument('--dest-format', metavar='FMT', 
                        help='grammar format (default: %(default)s)', 
                        default='pmcfg')
    parser.add_argument('--dest-enc', metavar='ENCODING', 
                        help='grammar encoding (default: %(default)s)', 
                        default='utf-8')
    parser.add_argument('--dest-opts', nargs='+', metavar='O',
                        help='space separated list of options O for writing ' \
                            'the grammar of the form key:value ' \
                            '(default: %(default)s)', 
                        default=[])
    parser.add_argument('--usage', nargs=0, help='show detailed information ' \
                        'about available tasks and input format/options', 
                        action=UsageAction)
    parser.set_defaults(func=run)
    return parser


class UsageAction(argparse.Action):
    """Custom action which shows extended help on available options.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        title_str = misc.bold("%s help" % sys.argv[0])
        help_str = "\n\n%s\n\n%s\n%s\n\n%s\n%s\n\n%s\n\n%s\n\n%s\n" \
            % (misc.bold('available input formats: '),
               misc.get_doc(treeinput.INPUT_FORMATS),
               misc.bold('available input options: '),
               misc.get_doc_opts(treeinput.INPUT_OPTIONS),
               misc.bold('available dest formats: '),
               misc.get_doc(FORMATS),
               misc.bold('available dest options: '),
               misc.get_doc_opts(FORMAT_OPTIONS))
        print("\n%s%s" % (title_str, help_str))
        sys.exit()


def run(args):
    """Run the grammar extraction.
    """
    sys.stderr.write("reading from '%s' in format '%s' and encoding '%s'\n" 
                     % (args.src, args.src_format, args.src_enc))
    sys.stderr.write("extracting grammar\n")
    grammar = {}
    cnt = 1
    for tree in getattr(treeinput, 
                        args.src_format)(args.src, args.src_enc, 
                                         **misc.options_dict \
                                         (args.src_opts)):
        extract(tree, grammar)
        if cnt % 100 == 0:
            sys.stderr.write("\r%d" % cnt)
        cnt += 1
    sys.stderr.write("writing grammar in format '%s', encoding '%s', to '%s'\n"
                     % (args.dest_format, args.dest_enc, args.dest))
    globals()[args.dest_format](grammar, args.dest, 
                                args.dest_enc, 
                                **misc.options_dict(args.dest_opts))
    sys.stderr.write("\n")


FORMATS = ['pmcfg']
FORMAT_OPTIONS = {}