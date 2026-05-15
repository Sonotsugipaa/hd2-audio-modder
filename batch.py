import sys
import os
from dataclasses import dataclass
from io import StringIO
import re

import env
import core



WHITESPACE_CHARS = { " ", "\t" }
QUOTE_CHARS = { "'", "\"", "`" }
SPECIAL_CHARS = set.update(WHITESPACE_CHARS, QUOTE_CHARS, { "\\" })
MAX_DISPLAY_LINE_LENGTH = 80


@dataclass
class ParsingContext:
    line: int = 0
    column: int = 0

    def move_forward(self, n=1):
        self.column += n

    def new_line(self, lines=1):
        self.column = 0
        self.line += 1


class ParseError(Exception):
    context: ParsingContext

    def __init__(self, ctx, msg):
        super().__init__(msg)
        self.context = ctx


class BadInstrError(RuntimeError):
    line_num: int | None

    def __init__(self, line_num, msg):
        super().__init__(msg)
        self.line_num = line_num


def parse_command_line_args(args):
    literal_args = False
    argn = len(args)
    i = 0
    input_files = [ ]
    output_file = None
    arg = None
    while True:
        arg = args[i]
        if arg.startswith("-o"):
            j = i+1
            if j < argn:
                output_file = args[j]
                i = j
            else:
                output_file = ""
        elif arg == "--":
            literal_args = True
            break
        else:
            input_files.append(arg)
        i += 1
        if i >= argn:
            break
    for arg in args[i:]:
        input_files.append(arg)
    return (output_file, input_files)


def parse_instr(line_ctr: int, line: str) -> line[str]:
    line_len = len(line)
    words = []
    word_buffer = StringIO()
    i = 0
    escape = False
    quote = None
    def get_buf_size(buf):
        buf.seek(0, os.SEEK_END)
        return buf.tell()
    while i < line_len:
        chr = line[i]
        chr_is_whitespace = (chr in WHITESPACE_CHARS)
        chr_matches_cur_quote = (chr == quote)
        chr_is_quote = (chr in QUOTE_CHARS)
        chr_begins_quote = (chr_is_quote and quote == None)
        chr_is_special = chr_is_whitespace or chr_begins_quote or chr_matches_cur_quote
        buf_size = get_buf_size(word_buffer)
        if escape:
            if chr_is_special or chr == "\\":
                word_buffer.write(chr)
                escape = False
            else:
                raise ParseError(ParsingContext(line_ctr, i), "trying to escape non-special character '{}'".format())
        else:
            if chr_begins_quote:
                quote = chr
            elif chr_matches_cur_quote:
                quote = None
            elif chr == "\\":
                escape = True
            elif quote == None:
                if chr_is_whitespace:
                    buf_size = get_buf_size(word_buffer)
                    if buf_size > 0:
                        words.append(word_buffer.getvalue())
                        word_buffer = StringIO()
                elif chr == "#":
                    if get_buf_size(word_buffer) > 0:
                        words.append(word_buffer.getvalue())
                    return words
                else:
                    word_buffer.write(chr)
            elif chr == "\\":
                word_buffer.write(chr)
            else:
                word_buffer.write(chr)
        i += 1
    if get_buf_size(word_buffer) > 0:
        words.append(word_buffer.getvalue())
    return words


class LineBuffer:
    _stored_partial_instr: list[str] | None
    file: None
    _line_ctr: int
    _eof: bool

    def __init__(self, file):
        self._stored_partial_instr = None
        self.file = file
        self._line_ctr = 0
        self._eof = False

    def _fetch_partial_instr(self) -> str:
        if self._eof:
            return None
        ln = self.file.readline()
        if ln:
            ln = parse_instr(self._line_ctr, ln.rstrip("\r\n"))
            return ln
        else:
            self._eof = True
            return None

    def fetch_instruction(self) -> list[str] | None:
        r = self._stored_partial_instr
        if r == None:
            r = [ ]
        else:
            self._stored_partial_instr = None
        while True:
            partial_instr = self._fetch_partial_instr()
            if partial_instr == None:
                if len(r) > 0:
                    self._line_ctr += 1
                    return r
                else:
                    return None
            if len(partial_instr) > 0:
                self._line_ctr += 1
                if partial_instr[0] == "...":
                    r += partial_instr[1:]
                else:
                    if len(r) > 0:
                        self._stored_partial_instr = partial_instr
                        return r
                    else:
                        r += partial_instr
        return r

    def current_line(self) -> int:
        return self._line_ctr


def interpret_instr(instr) -> tuple(str, list[str], list[str]):
    """
    Returns a tuple containing:
    - a string describing the command;
    - a list of arguments, or None if no non-variadic argument is expected;
    - a list containing values of the variadic argument, or None if no
      variadic argument is expected.
    """
    VARIADIC = "?VARARG"
    def match_word_seq(lh: list[str], *rh_match_lists: tuple(str | list[str])):
        lh_len = len(lh)
        rh_len = len(rh_match_lists)
        lengths_match = (lh_len == rh_len)
        if rh_match_lists[-1] == VARIADIC:
            rh_match_lists = (*rh_match_lists[:-1], None)
            if lh_len > rh_len:
                lengths_match = True
        for i in range(0, rh_len):
            rh_does_match = False
            rh_list = rh_match_lists[i]
            if type(rh_list) == str:
                rh_list = [ rh_list ]
            elif rh_list == None:
                continue
            for rh_i in rh_list:
                if rh_i == None or lh[i] == rh_i:
                    rh_does_match = True
                    break
            if not rh_does_match:
                return False
        return True
    # ---
    instr_len = len(instr)
    if match_word_seq(instr, "use", ["archive", "archives"], VARIADIC):
        return ("use archive", None, instr[2:])
    elif match_word_seq(instr, "new", "set", None):
        return ("new set", [instr[2]], None)
    elif match_word_seq(instr, "assign", "to", None, VARIADIC):
        return ("assign to", [instr[2]], instr[3:])
    elif match_word_seq(instr, "append", "to", None, VARIADIC):
        return ("append to", [instr[2]], instr[3:])
    elif instr_len >= 1:
        instr_fam = instr[0]
        instr = instr[1:]
        match instr_fam:
            case "wd":
                if match_word_seq(instr, "rel"):
                    return ("wd rel", [instr[1]], None)
                elif match_word_seq(instr, "home"):
                    return ("wd home", [instr[1]], None)
            case "replace":
                if match_word_seq(instr, None, "with", None):
                    return ("replace one", [instr[0]], [instr[2]])
                elif match_word_seq(instr, "cues", "in", None, "with", VARIADIC):
                    return ("replace many", [instr[2]], instr[4:])
            case "set":
                if match_word_seq(instr, "sequence", None, "gain", None, "db"):
                    return ("set seq gain", [instr[1]], [instr[3]])
                elif match_word_seq(instr, "sequence", None, "random"):
                    return ("set seq random", [instr[1]], None)
                elif match_word_seq(instr, "sequence", None, "not", "random"):
                    return ("set seq not random", [instr[1]], None)
                elif match_word_seq(instr, "cue", None, "gain", None, "db"):
                    return ("set cue gain", [instr[1]], [instr[3]])
    return None


def remap_list_indices(src, dst):
    """Returns an list of contiguous integer numbers containing `dst` elements,
    starting from 0 and reaching up to `src`.

    If `src` < `dst`, the distribution of the values in the list is as uniform as possible;
    if `src` >= `dst`, the returned list is `range(0, dst)`.
    
    For example:
    - `remap_list_indices(3, 9)` returns `[0, 0, 0, 1, 1, 1, 2, 2, 2]`;
    - `remap_list_indices(3, 3)` returns `[0, 1, 2]`;
    - `remap_list_indices(3, 2)` returns `[0, 1]`;
    - `remap_list_indices(3, 7)` returns something similar to `[0, 0, 1, 1, 2, 2, 2]`.
    """
    if src >= dst: return range(0, dst)
    return [ (i * src // dst) for i in range(0, dst) ]


class ScriptContext:
    working_dir: str
    archives: list[str]
    sets: dict[str, set(str)]
    cue_replacements_by_cue:  dict[int, str]
    cue_replacements_by_file: dict[str, set(int)]
    set_seq_gain: dict[int, float]
    set_seq_random: dict[int, bool]
    set_cue_gain: dict[int, float]

    def __init__(self):
        self.working_dir = ""
        self.archives = [ ]
        self.sets = dict()
        self.cue_replacements_by_cue = dict()
        self.cue_replacements_by_file = dict()
        self.set_seq_gain = dict()
        self.set_seq_random = dict()
        self.set_cue_gain = dict()

    def describe(self):
        return [
            "archives: {}".format(self.archives),
            "sets: {}".format(self.sets),
            "replacements: {}".format(self.cue_replacements_by_file),
            "set sequences gain: {}".format(self.set_seq_gain),
            "set sequences randomness: {}".format(self.set_seq_random),
            "set cues gain: {}".format(self.set_cue_gain) ]

    def replace_cues(self, cue_list, file_list):
        file_idx_remap = remap_list_indices(len(file_list), len(cue_list))
        append_repl_by_file = dict()
        for i in range(0, len(cue_list)):
            file = os.path.join(self.working_dir, file_list[file_idx_remap[i]])
            cue = cue_list[i]
            if file not in append_repl_by_file:
                append_repl_by_file[file] = { cue }
            else:
                append_repl_by_file[file].add(cue)
        for append_file in append_repl_by_file:
            for append_cue in append_repl_by_file[append_file]:
                if append_cue in self.cue_replacements_by_cue:
                    self.cue_replacements_by_file.pop(self.cue_replacements_by_cue[append_cue], None)
                self.cue_replacements_by_cue[append_cue] = append_file
                if append_file not in self.cue_replacements_by_file:
                    self.cue_replacements_by_file[append_file] = { append_cue }
                else:
                    self.cue_replacements_by_file[append_file].add(append_cue)


def run_instr(ctx: ScriptContext, instr_words: list[str]):
    if len(instr_words) < 1:
        raise ValueError("empty instruction")
    instr = interpret_instr(instr_words)
    if instr == None:
        return
    match instr[0]:
        case "wd rel":
            ctx.working_dir = os.path.normpath(instr[1][0])
        case "wd home":
            envvar = "USERPROFILE" if (env.SYSTEM == "Windows") else "HOME"
            if envvar not in os.environ:
                raise RuntimeError("environment variable '{}' not set".format(envvar))
            ctx.working_dir = os.path.normpath(os.path.join(os.environ[envvar], instr[1][0]))
        case "use archive":
            ctx.archives += instr[2]
        case "new set":
            ctx.sets[instr[1][0]] = set()
        case "assign to":
            ctx.sets[instr[1][0]] = set(instr[2])
        case "append to":
            set_name = instr[1][0]
            if set_name not in ctx.sets:
                ctx.sets[set_name] = set(instr[2])
            else:
                ctx.sets[set_name].update(instr[2])
        case "replace one":
            cue = int(instr[1][0])
            file = os.path.join(ctx.working_dir, instr[2][0])
            if cue in ctx.cue_replacements_by_cue:
                ctx.cue_replacements_by_file.pop(ctx.cue_replacements_by_cue[cue], None)
            ctx.cue_replacements_by_cue[cue] = file
            if file not in ctx.cue_replacements_by_file:
                ctx.cue_replacements_by_file[file] = { cue }
            else:
                ctx.cue_replacements_by_file[file].add(cue)
        case "replace many":
            set_name = instr[1][0]
            if set_name not in ctx.sets:
                raise KeyError("set '{}' does not exist".format(set_name))
            cue_list = [ int(i) for i in ctx.sets[set_name] ]
            file_list = list(set(instr[2])) # remove duplicates
            ctx.replace_cues(cue_list, file_list)
        case "set seq gain":
            ctx.set_seq_gain[int(instr[1][0])] = float(instr[2][0])
        case "set seq random":
            ctx.set_seq_random[int(instr[1][0])] = True
        case "set seq not random":
            ctx.set_seq_random[int(instr[1][0])] = False
        case "set cue gain":
            ctx.set_cue_gain[int(instr[1][0])] = float(instr[2][0])
        case _:
            match len(instr_words):
                case 0: raise(BadInstrError(None, "empty instruction"))
                case 1: raise(BadInstrError(None, "bad instruction: {}"          .format(instr_words[1])))
                case 2: raise(BadInstrError(None, "bad instruction: {} {}"       .format(*instr_words[:2])))
                case 3: raise(BadInstrError(None, "bad instruction: {} {} {}"    .format(*instr_words[:3])))
                case _: raise(BadInstrError(None, "bad instruction: {} {} {} ...".format(*instr_words[:3])))


# Commands to describe in documentation:
# - wd rel DIR[1]
# - wd home DIR[1]
# - use archive ARCHIVE[1..N]
# - use archives ARCHIVE[1..N] # same semantics as above
# - new set SET_NAME[1]
# - assign to SET_NAME[1] STRING[1..N]
# - append to SET_NAME[1] STRING[1..N]
# - replace ID[1] with FILE[1]
# - replace cues in ID_SET[1] with FILE[1..N]
# - set sequence ID[1] gain GAIN[1] db
# - set sequence ID[1] random
# - set sequence ID[1] not random
# - set cue ID[1] gain GAIN[1] db
def run_script(ctx: ScriptContext, script_filename: str, output_file: str):
    with open(script_filename, "rt") as file:
        rdr = LineBuffer(file)
        instr = rdr.fetch_instruction()
        while instr != None:
            try:
                run_instr(ctx, instr)
            except BadInstrError as e:
                if e.line_num == None:
                    e.line_num = rdr.current_line()
                raise e
            instr = rdr.fetch_instruction()


def print_cue_replacements(replacements):
    def print_ln(ln):
        print("    {}".format(ln[0]), end='')
        for cue in ln[1:]:
            print(" {}".format(cue), end='')
        print()
    print("Replacing the following cues...")
    for repl_file in replacements:
        print("  ", end='')
        print(repl_file)
        ln = [ ]
        ln_len = 3
        for repl_cue in replacements[repl_file]:
            repl_cue = str(repl_cue)
            repl_cue_len = len(repl_cue)
            if ln_len + repl_cue_len > MAX_DISPLAY_LINE_LENGTH:
                if len(ln) == 0:
                    print("    {}".format(repl_cue))
                else:
                    print_ln(ln)
                    ln = [ repl_cue ]
                    ln_len = 3 + repl_cue_len
            else:
                ln.append(repl_cue)
                ln_len += repl_cue_len
        if len(ln) > 0:
            print_ln(ln)


def run(app_state, output_file: str | None, input_files: list[str]):
    import_error_is_critical = True # may be opt-out from the command line in the future
    mod_handler = core.ModHandler.get_instance(None)
    mod_handler.create_new_mod("default")
    mod = mod_handler.get_active_mod()

    match output_file:
        case None:
            raise ValueError("no output specified")
        case "":
            raise ValueError("null output specified")
    ctx = ScriptContext()
    for i_file in input_files:
        print("Running batch script '{}'...".format(i_file))
        run_script(ctx, i_file, output_file)

    for archive_id in ctx.archives:
        archive_file = os.path.join(app_state.game_data_path, archive_id)
        if not mod.load_archive_file(archive_file):
            print("Couldn't find archive '{}'".format(archive_id))

    print_cue_replacements(ctx.cue_replacements_by_file)

    if import_error_is_critical:
        mod.import_files(ctx.cue_replacements_by_file)
    else:
        # One import for each file: if one file is missing, the rest can
        # still be imported
        for repl_file in ctx.cue_replacements_by_file:
            single_repl = { repl_file: ctx.cue_replacements_by_file[repl_file] }
            try:
                mod.import_files(single_repl)
            except OSError as e:
                print("Skipping replacement from '{}':  {}".format(repl_file, e))

    output_path = os.path.split(output_file)
    print("Writing patch in '{}' as '{}'".format(*output_path))
    mod.write_patch(*output_path)
