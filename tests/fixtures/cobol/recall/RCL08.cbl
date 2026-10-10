       IDENTIFICATION DIVISION.
       PROGRAM-ID. RCL08.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           COPY XSELECT.
           COPY XSELST.
       DATA DIVISION.
       FILE SECTION.
       FD  X-IN.
       01  X-IN-REC                PIC X(80).
       FD  X-OUT.
       01  X-OUT-REC               PIC X(80).
       WORKING-STORAGE SECTION.
           COPY XSTATUS.
           COPY XSECRET REPLACING ==:PFX:== BY ==WS==
                                  ==:PWD:== BY =='Tr0ub4dor&3'==.
           COPY XTABLE REPLACING LEADING ==TPL-== BY ==WS-==.
           COPY XAMOUNT REPLACING ==:T:== BY ==WS-TOT==.
       01  WS-DB-PASSWORD          PIC X(12).
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT X-IN OUTPUT X-OUT
           PERFORM WORK-PARA
           COPY XFINISH.
       WORK-PARA.
           DISPLAY 'WORK'.
       ORPHAN-PARA.
           DISPLAY 'NEVER'.
