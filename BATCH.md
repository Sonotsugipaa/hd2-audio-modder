# Batch operations

It is possible to run batch operations through the command line without using the graphical interface, by using batch scripts.

## Batch script language

A script is a sequence of instructions:  
each instruction may span a single line, or
multiple lines if every line after the first is preceded by an ellipsis (`...`).

For example, the following code blocks are all semantically identical instructions:

```
use archives 00001 00002 00003
```

---

```
use archives 00001
...          00002
...          00003
```

---

```
use archives
... 00001 00002 00003
```

---

```
use
... archives 00001 00002 00003
```

Lists of arbitrary strings (hereinafter "**words**"), such as filenames, are all separated by whitespaces:  
words that include whitespaces can be delimited using quotes, double quotes or backticks;  
alternatively, each whitespace can be escaped with a backslash.

For example, the following words are equivalent:

- `C:/Users/John\ Doe\ 1998`
- `"C:/Users/John Doe 1998"`
- `'C:/Users/John Doe 1998'`
- (markdown is finnicky with escaped backticks (\`), but you get the idea)

In every line, everything after a hash (#) is ignored.

### Types of instruction

- `wd rel PATH`:  
  changes the script's working directory to `PATH`, relative to the path specified by the environment variable `HD2AM_BATCH_REL_ROOT`; if said variable is not set, the working directory of the process is used instead
- `wd home PATH`:  
  changes the script's working directory to `PATH`, relative to the user's home
- `use archive ARCHIVE_NAME...` or  
  `use archives ARCHIVE_NAME...`:  
  load the specified archives from the game's data directory ("archive" and "archives" are equivalent - multiple archives can be loaded with `use archive AR_1 AR_2 AR_3`)
- `new set SET_NAME`:  
  creates an empty set named `SET_NAME`
- `assign to SET_NAME VALUE...`:  
  assigns the given values to the `SET_NAME` set
- `append to SET_NAME VALUE...`:  
  appends the given values to the `SET_NAME` set
- `replace CUE_ID with FILE`:  
  imports the file `FILE` over the cue `CUE_ID`
- `replace cues in SET_NAME with FILE...`:  
  imports files listed in `FILE...` over each cue in the set `SET_NAME`;
  if the set of cues is bigger than the list of files, the latter is "stretched" to fit the former
- `replace sequence SEQ_ID with FILE...`:  
  same as above, but cues in the given Wwise sequence will be replaced instead of those assigned to a set
- `set sequence SEQ_ID random`:  
  Specify that cues in the sequence should play in random order
- `set sequence SEQ_ID not random`:  
  Specify that cues in the sequence should play in sequential order
- `set gain GAIN db to sequence SEQ_ID...` or  
  `set gain GAIN db to sequences SEQ_ID...`:  
  set the make-up gain of the given sequences
- `set gain GAIN db to cue CUE_ID...` or  
  `set gain GAIN db to cues CUE_ID...`:  
  set the make-up gain of the given cues
- `set gain GAIN db to each cue in SET_NAME`:  
  set the make-up gain of the cues in the given set
- `set gain GAIN db to each sequence in SET_NAME`:  
  set the make-up gain of the sequences in the given set
- `add gain ...`:  
  same as the matching `set gain ...` instruction, but the specified number of decibels is added to the original/current make-up gain

### Example batch file

```
use archives
... 27cb3df21f6599fd # Gunship
... 079529fe7dd7c0cb # Trooper
... 9e430d763af434c1 # env_bots

assign to  gunship_engine
... 130859057 32047585 42427440
... 418022432 642684067 949084344
... 352230493 975864829 933775856
replace cues in gunship_engine with "helicopter propellers.wem"

assign to  trooper_alert
... 308582977 441640224 484231469
... 924298843 1022900263
replace cues in trooper_alert  with annoyedbot.wem

# fusion cannon shot
replace sequence 716573335
... with explosion_1.wem explosion_2.wem
...      explosion_3.wem explosion_4.wem

replace 523479376060321966 with poptop-commissar.wem

add gain  2 db to  cue       523479376060321966
add gain -3 db to  cues in   gunship_engine
add gain 99 db to  sequence  716573335
```

### Running a batch script

In order to run a batch script, run the application from your shell as such:  
`python audio_modder.py -o OUTPUT_PATCH.patch_0 BATCH_SCRIPT.txt`

Multiple scripts can be used to generate a single patch file:  
`python audio_modder.py -o 9ba.patch_0 scr1.txt scr2.txt`  
... reads "*scr1.txt*" then "*scr2.txt*", and generates "*9ba.patch_0*" (and possibly "*9ba.patch_0.stream*").

Furthermore, *multiple* patch files can be generated, one for every "-o" argument pair:  `python audio_modder.py -o 9ba.patch_0 scr1.txt -o 9ba.patch_1 scr2.txt scr3.txt`  
... will:

1. generate "*9ba.patch_0*" using "*scr1.txt*";
2. reset the program's state;
3. generate "*9ba.patch_1*" using "*scr2.txt*" and "*scr3.txt*".

Note that generating multiple patches at once is **much faster** than running `audio_modder.py` once for each patch.

### Specifying the default script working directory

With PowerShell:  
```
$env:HD2AM_BATCH_REL_ROOT = 'C:\Users\John Doe\Modding\HD2'
python audio_modder.py -o OUT.patch_0 IN.txt
# this may be incorrect, I'm not familiar with PowerShell
```

With Bash:  
```
export HD2AM_BATCH_REL_ROOT=$HOME/Modding/HD2
python3 audio_modder.py -o OUT.patch_0 IN.txt
# ----- OR -----
HD2AM_BATCH_REL_ROOT=$HOME/Modding/HD2 python3 audio_modder.py -o OUT.patch_0 IN.txt
```
