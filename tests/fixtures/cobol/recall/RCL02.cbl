       IDENTIFICATION DIVISION.
       PROGRAM-ID. RCL02.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCT-FILE ASSIGN TO ACCTIN
               FILE STATUS IS WS-ACCT-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD  ACCT-FILE.
       01  ACCT-REC                PIC X(100).
       WORKING-STORAGE SECTION.
           COPY RECSHARE.
           COPY CUSTLAYOUT.
       01  WS-ACCT-STATUS          PIC XX.
       01  WS-BALANCE              PIC S9(7)V99 COMP-3.
       01  WS-BALANCE-X            REDEFINES WS-BALANCE
                                       PIC X(5).
       01  WS-RET-CODE             PIC S9(4) COMP.
       01  WS-RET-BYTES            REDEFINES WS-RET-CODE.
           05  WS-RET-HI               PIC X.
           05  WS-RET-LO               PIC X.
       01  WS-COUNT                PIC 9(3) VALUE 0.
       01  WS-TABLE.
           05  WS-ENTRY OCCURS 1 TO 50 TIMES DEPENDING ON WS-COUNT
                                       PIC X(20).
       01  WS-TABLE-2.
           05  WS-ITEM
                   OCCURS 1 TO 99 TIMES
                   DEPENDING ON WS-COUNT    PIC X(8).
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT ACCT-FILE
           READ ACCT-FILE
           CLOSE ACCT-FILE
           STOP RUN.
