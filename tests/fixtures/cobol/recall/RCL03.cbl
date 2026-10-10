       IDENTIFICATION DIVISION.
       PROGRAM-ID. RCL03.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY RECSHARE.
           COPY CUSTLAYOUT.
       01  WS-SMTP-PASSWORD        PIC X(12) VALUE 'Mailer2024!'.
       01  WS-CONN-STR             PIC X(60) VALUE
           'DSN=PRODDB;UID=BATCH;PWD=Xy7#kq;'.
       01  WS-N                    PIC 9 VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM P1 THRU P6
           STOP RUN.
           DISPLAY 'NEVER RUNS'.
       P1.
           ADD 1 TO WS-N.
       P2.
           ADD 1 TO WS-N.
       P3.
           ADD 1 TO WS-N.
       P4.
           ADD 1 TO WS-N.
       P5.
           ADD 1 TO WS-N.
       P6.
           ADD 1 TO WS-N.
           GOBACK.
       OLD-REPORT.
           DISPLAY 'OLD'.
