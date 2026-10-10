       IDENTIFICATION DIVISION.
       PROGRAM-ID. RCL01.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUST-FILE ASSIGN TO CUSTIN
               ORGANIZATION IS SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  CUST-FILE.
       01  CUST-REC                PIC X(80).
       WORKING-STORAGE SECTION.
           COPY RECSHARE.
           COPY CUSTLAYOUT.
       01  WS-DB-PASSWORD          PIC X(16).
       01  WS-CUST-ID              PIC X(10).
       01  WS-I                    PIC 9(4) VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT CUST-FILE
           MOVE 'Pr0d#Secret9' TO WS-DB-PASSWORD
           ACCEPT WS-CUST-ID
           GO TO STEP-01.
       STEP-01.
           ADD 1 TO WS-I
           GO TO STEP-02.
       STEP-02.
           ADD 1 TO WS-I
           GO TO STEP-03.
       STEP-03.
           ADD 1 TO WS-I
           GO TO STEP-04.
       STEP-04.
           ADD 1 TO WS-I
           GO TO STEP-05.
       STEP-05.
           ADD 1 TO WS-I
           GO TO STEP-06.
       STEP-06.
           ADD 1 TO WS-I
           GO TO STEP-07.
       STEP-07.
           ADD 1 TO WS-I
           GO TO STEP-08.
       STEP-08.
           ADD 1 TO WS-I
           GO TO STEP-09.
       STEP-09.
           ADD 1 TO WS-I
           GO TO STEP-10.
       STEP-10.
           ADD 1 TO WS-I
           GO TO DONE-PARA.
       DONE-PARA.
           CLOSE CUST-FILE
           STOP RUN.
