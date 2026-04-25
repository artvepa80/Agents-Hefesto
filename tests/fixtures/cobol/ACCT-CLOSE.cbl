      *****************************************************************
      * Purpose: Account closing program (2nd reference to copybook)
      * Rules: COPYBOOK_BLAST_RADIUS (2nd reference)
      * Expected: 0 findings (same as ACCT-OPEN - informational only)
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCT-CLOSE.
       AUTHOR. ACCOUNT-TEAM.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY CUST-RECORD.

       01  WS-SQLCODE                   PIC S9(9) COMP.
       01  WS-CLOSE-REASON              PIC X(50).
       01  WS-FINAL-BALANCE             PIC S9(11)V99.
       01  WS-REFUND-AMOUNT             PIC S9(9)V99.

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           PERFORM 1000-INITIALIZE.
           PERFORM 2000-RETRIEVE-CUSTOMER.
           PERFORM 3000-PROCESS-CLOSURE.
           PERFORM 4000-FINALIZE.
           STOP RUN.

       1000-INITIALIZE.
           DISPLAY 'Account Closure Process Started'.
           MOVE 'CUSTOMER REQUEST' TO WS-CLOSE-REASON.
           MOVE ZERO TO WS-FINAL-BALANCE.
           MOVE ZERO TO WS-REFUND-AMOUNT.

       2000-RETRIEVE-CUSTOMER.
           MOVE 123456789 TO CUST-ID.

           EXEC SQL
               SELECT NAME, STREET, CITY, STATE, ZIP,
                      PHONE, EMAIL, BALANCE, STATUS
               INTO :CUST-NAME, :CUST-STREET, :CUST-CITY, :CUST-STATE,
                    :CUST-ZIP, :CUST-PHONE, :CUST-EMAIL,
                    :CUST-ACCOUNT-BALANCE, :CUST-STATUS
               FROM CUSTOMERS
               WHERE CUSTOMER_ID = :CUST-ID
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = ZERO
               DISPLAY 'Customer found: ' CUST-NAME
               MOVE CUST-ACCOUNT-BALANCE TO WS-FINAL-BALANCE
           ELSE
               DISPLAY 'Customer not found: ' WS-SQLCODE
           END-IF.

       3000-PROCESS-CLOSURE.
           IF WS-FINAL-BALANCE > ZERO
               MOVE WS-FINAL-BALANCE TO WS-REFUND-AMOUNT
               DISPLAY 'Refund amount: ' WS-REFUND-AMOUNT
           END-IF.

           MOVE 'CLOSED' TO CUST-STATUS.

           EXEC SQL
               UPDATE CUSTOMERS
               SET STATUS = :CUST-STATUS,
                   BALANCE = 0,
                   LAST_ACTIVITY = CURRENT DATE
               WHERE CUSTOMER_ID = :CUST-ID
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = ZERO
               DISPLAY 'Account closed successfully'
           ELSE
               DISPLAY 'Account closure failed: ' WS-SQLCODE
           END-IF.

       4000-FINALIZE.
           DISPLAY 'Account Closure Process Complete'.
           DISPLAY 'Reason: ' WS-CLOSE-REASON.
           DISPLAY 'Final balance refunded: ' WS-REFUND-AMOUNT.
           DISPLAY 'Customer ID: ' CUST-ID.
