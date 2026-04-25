      *****************************************************************
      * Purpose: Well-structured COBOL program with proper practices
      * Rules: None (negative test - demonstrates clean code)
      * Expected: 0 findings
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLEAN-PROG.
       AUTHOR. HEFESTO-AI.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-370.
       OBJECT-COMPUTER. IBM-370.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-CUSTOMER-RECORD.
           05  WS-CUSTOMER-ID           PIC 9(9).
           05  WS-CUSTOMER-NAME         PIC X(50).
           05  WS-ACCOUNT-BALANCE       PIC S9(11)V99 COMP-3.
           05  WS-ACCOUNT-STATUS        PIC X(10).

       01  WS-DB-STATUS                 PIC X(2).
       01  WS-SQLCODE                   PIC S9(9) COMP.
       01  WS-TRANSACTION-COUNT         PIC 9(5) VALUE ZERO.
       01  WS-EOF-FLAG                  PIC X VALUE 'N'.
           88  EOF-REACHED              VALUE 'Y'.

       01  WS-QUERY                     PIC X(200).

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           PERFORM 1000-INITIALIZE.
           PERFORM 2000-PROCESS-CUSTOMERS
               UNTIL EOF-REACHED.
           PERFORM 3000-FINALIZE.
           STOP RUN.

       1000-INITIALIZE.
           MOVE ZERO TO WS-TRANSACTION-COUNT.
           MOVE 'N' TO WS-EOF-FLAG.
           DISPLAY 'Starting customer processing...'.

       2000-PROCESS-CUSTOMERS.
           PERFORM 2100-READ-CUSTOMER.
           IF NOT EOF-REACHED
               PERFORM 2200-VALIDATE-CUSTOMER
               IF WS-DB-STATUS = '00'
                   PERFORM 2300-UPDATE-BALANCE
               END-IF
           END-IF.

       2100-READ-CUSTOMER.
      * Simulates reading customer record
           ADD 1 TO WS-TRANSACTION-COUNT.
           IF WS-TRANSACTION-COUNT > 100
               MOVE 'Y' TO WS-EOF-FLAG
           ELSE
               MOVE 123456789 TO WS-CUSTOMER-ID
               MOVE 'SAMPLE CUSTOMER' TO WS-CUSTOMER-NAME
               MOVE 1000.50 TO WS-ACCOUNT-BALANCE
               MOVE 'ACTIVE' TO WS-ACCOUNT-STATUS
               MOVE '00' TO WS-DB-STATUS
           END-IF.

       2200-VALIDATE-CUSTOMER.
      * Validates customer data with parameterized query
           MOVE 'SELECT STATUS FROM CUSTOMERS WHERE ID = ?'
               TO WS-QUERY.
           EXEC SQL
               SELECT ACCOUNT_STATUS
               INTO :WS-ACCOUNT-STATUS
               FROM CUSTOMERS
               WHERE CUSTOMER_ID = :WS-CUSTOMER-ID
           END-EXEC.
           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = ZERO
               MOVE '00' TO WS-DB-STATUS
           ELSE
               MOVE '99' TO WS-DB-STATUS
               DISPLAY 'SQL Error: ' WS-SQLCODE
           END-IF.

       2300-UPDATE-BALANCE.
      * Updates balance using parameterized SQL
           EXEC SQL
               UPDATE ACCOUNTS
               SET BALANCE = :WS-ACCOUNT-BALANCE
               WHERE CUSTOMER_ID = :WS-CUSTOMER-ID
           END-EXEC.
           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE NOT = ZERO
               DISPLAY 'Update failed for customer: '
                   WS-CUSTOMER-ID
           END-IF.

       3000-FINALIZE.
           DISPLAY 'Total transactions processed: '
               WS-TRANSACTION-COUNT.
           DISPLAY 'Processing complete.'.
