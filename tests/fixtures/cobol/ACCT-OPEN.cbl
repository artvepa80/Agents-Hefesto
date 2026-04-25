      *****************************************************************
      * Purpose: Account opening program (references CUST-RECORD.cpy)
      * Rules: COPYBOOK_BLAST_RADIUS (1st reference)
      * Expected: 0 findings (copybook blast radius is informational
      *           in Phase 1 - single-file detection only)
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCT-OPEN.
       AUTHOR. ACCOUNT-TEAM.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY CUST-RECORD.

       01  WS-SQLCODE                   PIC S9(9) COMP.
       01  WS-NEW-ACCOUNT-ID            PIC 9(9).
       01  WS-INITIAL-DEPOSIT           PIC S9(9)V99.
       01  WS-APPROVAL-STATUS           PIC X(10).

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           PERFORM 1000-INITIALIZE.
           PERFORM 2000-CREATE-CUSTOMER.
           PERFORM 3000-OPEN-ACCOUNT.
           PERFORM 4000-FINALIZE.
           STOP RUN.

       1000-INITIALIZE.
           DISPLAY 'Account Opening Process Started'.
           MOVE ZERO TO WS-NEW-ACCOUNT-ID.
           MOVE ZERO TO WS-INITIAL-DEPOSIT.
           MOVE 'PENDING' TO WS-APPROVAL-STATUS.

       2000-CREATE-CUSTOMER.
           MOVE 123456789 TO CUST-ID.
           MOVE 'JOHN DOE' TO CUST-NAME.
           MOVE '123 MAIN ST' TO CUST-STREET.
           MOVE 'ANYTOWN' TO CUST-CITY.
           MOVE 'CA' TO CUST-STATE.
           MOVE 12345 TO CUST-ZIP.
           MOVE '555-1234' TO CUST-PHONE.
           MOVE 'john.doe@example.com' TO CUST-EMAIL.
           MOVE 0.00 TO CUST-ACCOUNT-BALANCE.
           MOVE 5000.00 TO CUST-CREDIT-LIMIT.
           MOVE 'ACTIVE' TO CUST-STATUS.
           MOVE '2026-04-25' TO CUST-CREATED-DATE.
           MOVE '2026-04-25' TO CUST-LAST-ACTIVITY.

           EXEC SQL
               INSERT INTO CUSTOMERS
               (CUSTOMER_ID, NAME, STREET, CITY, STATE, ZIP,
                PHONE, EMAIL, BALANCE, CREDIT_LIMIT, STATUS,
                CREATED_DATE, LAST_ACTIVITY)
               VALUES
               (:CUST-ID, :CUST-NAME, :CUST-STREET, :CUST-CITY,
                :CUST-STATE, :CUST-ZIP, :CUST-PHONE, :CUST-EMAIL,
                :CUST-ACCOUNT-BALANCE, :CUST-CREDIT-LIMIT,
                :CUST-STATUS, :CUST-CREATED-DATE, :CUST-LAST-ACTIVITY)
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = ZERO
               DISPLAY 'Customer record created: ' CUST-ID
           ELSE
               DISPLAY 'Customer creation failed: ' WS-SQLCODE
           END-IF.

       3000-OPEN-ACCOUNT.
           MOVE 1000.00 TO WS-INITIAL-DEPOSIT.
           COMPUTE CUST-ACCOUNT-BALANCE =
               CUST-ACCOUNT-BALANCE + WS-INITIAL-DEPOSIT.

           EXEC SQL
               UPDATE CUSTOMERS
               SET BALANCE = :CUST-ACCOUNT-BALANCE
               WHERE CUSTOMER_ID = :CUST-ID
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = ZERO
               MOVE 'APPROVED' TO WS-APPROVAL-STATUS
               DISPLAY 'Account opened with balance: '
                   CUST-ACCOUNT-BALANCE
           ELSE
               DISPLAY 'Account opening failed: ' WS-SQLCODE
           END-IF.

       4000-FINALIZE.
           DISPLAY 'Account Opening Process Complete'.
           DISPLAY 'Status: ' WS-APPROVAL-STATUS.
           DISPLAY 'Customer ID: ' CUST-ID.
