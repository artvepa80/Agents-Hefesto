      *****************************************************************
      * Purpose: Variable-length table with OCCURS DEPENDING ON
      * Rules: OCCURS_DEPENDING_ON (positive test)
      * Expected: 1 MEDIUM finding (line ~24 - runtime size ambiguity)
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DYNAMIC-TABLE.
       AUTHOR. REPORT-TEAM.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TABLE-COUNT               PIC 9(4) VALUE ZERO.
       01  WS-MAX-ENTRIES               PIC 9(4) VALUE 500.
       01  WS-CURRENT-INDEX             PIC 9(4).

       01  WS-TRANSACTION-TABLE.
      * MEDIUM: Variable-length table with OCCURS DEPENDING ON (line ~24)
      * Runtime size is determined by WS-TABLE-COUNT
           05  WS-TRANS-ENTRY OCCURS 1 TO 500 TIMES
               DEPENDING ON WS-TABLE-COUNT.
               10  WS-TRANS-ID          PIC 9(9).
               10  WS-TRANS-DATE        PIC X(10).
               10  WS-TRANS-AMOUNT      PIC S9(9)V99 COMP-3.
               10  WS-TRANS-TYPE        PIC X(1).
               10  WS-TRANS-STATUS      PIC X(10).

       01  WS-SQLCODE                   PIC S9(9) COMP.
       01  WS-TOTAL-AMOUNT              PIC S9(11)V99 COMP-3.
       01  WS-EOF-FLAG                  PIC X VALUE 'N'.
           88  EOF-REACHED              VALUE 'Y'.

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           PERFORM 1000-INITIALIZE.
           PERFORM 2000-LOAD-TRANSACTIONS.
           PERFORM 3000-PROCESS-TABLE.
           PERFORM 4000-FINALIZE.
           STOP RUN.

       1000-INITIALIZE.
           DISPLAY 'Transaction Table Processing Started'.
           MOVE ZERO TO WS-TABLE-COUNT.
           MOVE ZERO TO WS-TOTAL-AMOUNT.
           MOVE 'N' TO WS-EOF-FLAG.

       2000-LOAD-TRANSACTIONS.
           EXEC SQL
               DECLARE TRANS_CURSOR CURSOR FOR
               SELECT TRANSACTION_ID, TRANSACTION_DATE, AMOUNT,
                      TYPE, STATUS
               FROM TRANSACTIONS
               WHERE STATUS = 'PENDING'
               ORDER BY TRANSACTION_DATE
           END-EXEC.

           EXEC SQL
               OPEN TRANS_CURSOR
           END-EXEC.

           PERFORM 2100-FETCH-TRANSACTION
               UNTIL EOF-REACHED OR WS-TABLE-COUNT = WS-MAX-ENTRIES.

           EXEC SQL
               CLOSE TRANS_CURSOR
           END-EXEC.

       2100-FETCH-TRANSACTION.
           ADD 1 TO WS-TABLE-COUNT.

           EXEC SQL
               FETCH TRANS_CURSOR
               INTO :WS-TRANS-ID(WS-TABLE-COUNT),
                    :WS-TRANS-DATE(WS-TABLE-COUNT),
                    :WS-TRANS-AMOUNT(WS-TABLE-COUNT),
                    :WS-TRANS-TYPE(WS-TABLE-COUNT),
                    :WS-TRANS-STATUS(WS-TABLE-COUNT)
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = 100
               MOVE 'Y' TO WS-EOF-FLAG
               SUBTRACT 1 FROM WS-TABLE-COUNT
           ELSE
               IF WS-SQLCODE NOT = ZERO
                   DISPLAY 'Fetch error: ' WS-SQLCODE
                   MOVE 'Y' TO WS-EOF-FLAG
                   SUBTRACT 1 FROM WS-TABLE-COUNT
               END-IF
           END-IF.

       3000-PROCESS-TABLE.
           DISPLAY 'Processing ' WS-TABLE-COUNT ' transactions'.

           PERFORM VARYING WS-CURRENT-INDEX FROM 1 BY 1
               UNTIL WS-CURRENT-INDEX > WS-TABLE-COUNT

               DISPLAY 'Transaction: ' WS-TRANS-ID(WS-CURRENT-INDEX)
               DISPLAY '  Date: ' WS-TRANS-DATE(WS-CURRENT-INDEX)
               DISPLAY '  Amount: ' WS-TRANS-AMOUNT(WS-CURRENT-INDEX)

               ADD WS-TRANS-AMOUNT(WS-CURRENT-INDEX)
                   TO WS-TOTAL-AMOUNT

           END-PERFORM.

       4000-FINALIZE.
           DISPLAY 'Transaction Processing Complete'.
           DISPLAY 'Transactions processed: ' WS-TABLE-COUNT.
           DISPLAY 'Total amount: ' WS-TOTAL-AMOUNT.
