on run argv
  set inPath to item 1 of argv
  set outPath to item 2 of argv
  with timeout of 240 seconds
    tell application "Keynote"
      activate
      close every document saving no
      open (POSIX file inPath)
      set n to 0
      repeat until (count of documents) > 0 or n > 90
        delay 1
        set n to n + 1
      end repeat
      delay 3
      set theDoc to front document
      set docName to name of theDoc
      export theDoc to (POSIX file outPath) as PDF
      close theDoc saving no
      return docName
    end tell
  end timeout
end run
