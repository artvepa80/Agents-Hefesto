      *****************************************************************
      * Purpose: Batch loop with PERFORM THRU spanning >5 paragraphs
      * Rules: PERFORM_THRU_CHAIN (positive test)
      * Expected: 1 HIGH finding (line ~36 - fragile execution chain)
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BATCH-LOOP.
       AUTHOR. BATCH-TEAM.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RECORD-COUNT              PIC 9(7) VALUE ZERO.
       01  WS-BATCH-TOTAL               PIC S9(11)V99 COMP-3.
       01  WS-RECORD-STATUS             PIC X(10).
       01  WS-ERROR-COUNT               PIC 9(5) VALUE ZERO.
       01  WS-EOF-FLAG                  PIC X VALUE 'N'.
           88  EOF-REACHED              VALUE 'Y'.

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           DISPLAY 'Batch Processing Started'.
           MOVE ZERO TO WS-BATCH-TOTAL.
           MOVE 'N' TO WS-EOF-FLAG.

           PERFORM 0100-OPEN-FILES.

           PERFORM UNTIL EOF-REACHED
      * HIGH: PERFORM THRU spanning 7 paragraphs (line ~36)
      * Fragile execution chain - any paragraph change breaks flow
               PERFORM 1000-INIT THRU 1060-CLEANUP
           END-PERFORM.

           PERFORM 9000-CLOSE-FILES.

           DISPLAY 'Batch Processing Complete'.
           DISPLAY 'Records processed: ' WS-RECORD-COUNT.
           DISPLAY 'Batch total: ' WS-BATCH-TOTAL.
           DISPLAY 'Errors: ' WS-ERROR-COUNT.
           STOP RUN.

       0100-OPEN-FILES.
           DISPLAY 'Opening batch files...'.
           MOVE 'OPEN' TO WS-RECORD-STATUS.

       1000-INIT.
           ADD 1 TO WS-RECORD-COUNT.
           IF WS-RECORD-COUNT > 1000
               MOVE 'Y' TO WS-EOF-FLAG
           END-IF.

       1010-READ.
           IF NOT EOF-REACHED
               MOVE 'ACTIVE' TO WS-RECORD-STATUS
           ELSE
               MOVE 'EOF' TO WS-RECORD-STATUS
           END-IF.

       1020-VALIDATE.
           IF WS-RECORD-STATUS = 'ACTIVE'
               DISPLAY 'Validating record: ' WS-RECORD-COUNT
           ELSE
               IF WS-RECORD-STATUS NOT = 'EOF'
                   ADD 1 TO WS-ERROR-COUNT
               END-IF
           END-IF.

       1030-PROCESS.
           IF WS-RECORD-STATUS = 'ACTIVE'
               DISPLAY 'Processing record: ' WS-RECORD-COUNT
               ADD 100.50 TO WS-BATCH-TOTAL
           END-IF.

       1040-WRITE.
           IF WS-RECORD-STATUS = 'ACTIVE'
               DISPLAY 'Writing output for: ' WS-RECORD-COUNT
           END-IF.

       1050-LOG.
           IF WS-RECORD-STATUS = 'ACTIVE'
               DISPLAY 'Logging transaction: ' WS-RECORD-COUNT
           ELSE
               IF WS-ERROR-COUNT > 0
                   DISPLAY 'Error logged for record: '
                       WS-RECORD-COUNT
               END-IF
           END-IF.

       1060-CLEANUP.
           IF WS-RECORD-STATUS NOT = 'EOF'
               MOVE 'PROCESSED' TO WS-RECORD-STATUS
           END-IF.

       9000-CLOSE-FILES.
           DISPLAY 'Closing batch files...'.
           MOVE 'CLOSED' TO WS-RECORD-STATUS.
