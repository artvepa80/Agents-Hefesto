      *****************************************************************
      * Purpose: Legacy batch program with spaghetti control flow
      * Rules: GOTO_EXCESSIVE (positive test)
      * Expected: 1 HIGH severity finding (23 GO TO statements, threshold >10)
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SPAGHETTI-LOGIC.
       AUTHOR. LEGACY-SYSTEM.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RECORD-COUNT              PIC 9(7) VALUE ZERO.
       01  WS-ERROR-COUNT               PIC 9(5) VALUE ZERO.
       01  WS-STATUS-CODE               PIC X(2).
       01  WS-PROCESS-FLAG              PIC X VALUE 'N'.
       01  WS-RETRY-COUNT               PIC 9(2) VALUE ZERO.
       01  WS-BATCH-ID                  PIC 9(9).

       PROCEDURE DIVISION.
       START-PROCESS.
           MOVE ZERO TO WS-RECORD-COUNT.
           MOVE ZERO TO WS-ERROR-COUNT.
           GO TO INIT-BATCH.

       INIT-BATCH.
           DISPLAY 'Initializing batch process...'.
           IF WS-BATCH-ID = ZERO
               MOVE 999999999 TO WS-BATCH-ID
               GO TO CHECK-STATUS
           ELSE
               GO TO MAIN-LOOP
           END-IF.

       CHECK-STATUS.
           IF WS-STATUS-CODE = '00'
               GO TO MAIN-LOOP
           ELSE
               IF WS-STATUS-CODE = '99'
                   GO TO ERROR-HANDLER
               ELSE
                   GO TO INIT-BATCH
               END-IF
           END-IF.

       MAIN-LOOP.
           ADD 1 TO WS-RECORD-COUNT.
           IF WS-RECORD-COUNT > 1000
               GO TO END-PROCESS
           END-IF.

           MOVE 'N' TO WS-PROCESS-FLAG.
           GO TO VALIDATE-RECORD.

       VALIDATE-RECORD.
           IF WS-RECORD-COUNT < 100
               MOVE 'Y' TO WS-PROCESS-FLAG
               GO TO PROCESS-RECORD
           ELSE
               IF WS-RECORD-COUNT > 900
                   GO TO SPECIAL-HANDLING
               ELSE
                   GO TO PROCESS-RECORD
               END-IF
           END-IF.

       PROCESS-RECORD.
           IF WS-PROCESS-FLAG = 'Y'
               DISPLAY 'Processing record: ' WS-RECORD-COUNT
               GO TO WRITE-OUTPUT
           ELSE
               GO TO SKIP-RECORD
           END-IF.

       WRITE-OUTPUT.
           MOVE '00' TO WS-STATUS-CODE.
           IF WS-STATUS-CODE = '00'
               GO TO MAIN-LOOP
           ELSE
               ADD 1 TO WS-ERROR-COUNT
               GO TO RETRY-LOGIC
           END-IF.

       SKIP-RECORD.
           DISPLAY 'Skipping record: ' WS-RECORD-COUNT.
           GO TO MAIN-LOOP.

       SPECIAL-HANDLING.
           DISPLAY 'Special handling for record: ' WS-RECORD-COUNT.
           MOVE 'Y' TO WS-PROCESS-FLAG.
           IF WS-ERROR-COUNT > 10
               GO TO ERROR-HANDLER
           ELSE
               GO TO PROCESS-RECORD
           END-IF.

       RETRY-LOGIC.
           ADD 1 TO WS-RETRY-COUNT.
           IF WS-RETRY-COUNT > 3
               MOVE '99' TO WS-STATUS-CODE
               GO TO ERROR-HANDLER
           ELSE
               DISPLAY 'Retrying...'
               MOVE ZERO TO WS-RETRY-COUNT
               GO TO PROCESS-RECORD
           END-IF.

       ERROR-HANDLER.
           DISPLAY 'Error occurred. Status: ' WS-STATUS-CODE.
           DISPLAY 'Error count: ' WS-ERROR-COUNT.
           IF WS-ERROR-COUNT < 100
               MOVE '00' TO WS-STATUS-CODE
               GO TO MAIN-LOOP
           ELSE
               GO TO ABORT-PROCESS
           END-IF.

       ABORT-PROCESS.
           DISPLAY 'Aborting batch process due to errors.'.
           DISPLAY 'Records processed: ' WS-RECORD-COUNT.
           GO TO END-PROCESS.

       END-PROCESS.
           DISPLAY 'Batch process complete.'.
           DISPLAY 'Total records: ' WS-RECORD-COUNT.
           DISPLAY 'Total errors: ' WS-ERROR-COUNT.
           STOP RUN.
