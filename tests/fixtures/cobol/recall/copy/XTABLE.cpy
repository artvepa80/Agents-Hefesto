       01  TPL-TABLE.
           05  TPL-COUNT             PIC 9(4) COMP.
           05  TPL-ENTRY OCCURS 1 TO 50 TIMES DEPENDING ON TPL-COUNT.
               COPY XTKEY.
