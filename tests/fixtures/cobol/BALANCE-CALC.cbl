      *****************************************************************
      * Purpose: Balance calculation with REDEFINES on packed decimal
      * Rules: REDEFINES_SENSITIVE (positive test)
      * Expected: 1 HIGH finding (line ~25 - REDEFINES on COMP-3)
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BALANCE-CALC.
       AUTHOR: ACCOUNTING-TEAM.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-ACCOUNT-DATA.
           05  WS-ACCOUNT-ID            PIC 9(9).
           05  WS-ACCOUNT-TYPE          PIC X(10).
           05  WS-ACCOUNT-BALANCE       PIC S9(11)V99 COMP-3.
      * HIGH: REDEFINES on packed decimal field (line ~25)
      * This allows raw byte manipulation of financial data
           05  WS-BALANCE-RAW REDEFINES WS-ACCOUNT-BALANCE
                                        PIC X(8).

       01  WS-TRANSACTION-DATA.
           05  WS-TRANS-AMOUNT          PIC S9(9)V99 COMP-3.
           05  WS-TRANS-TYPE            PIC X(1).
               88  TRANS-DEBIT          VALUE 'D'.
               88  TRANS-CREDIT         VALUE 'C'.

       01  WS-CALCULATED-BALANCE        PIC S9(11)V99 COMP-3.
       01  WS-BALANCE-DISPLAY           PIC $$$,$$$,$$9.99.
       01  WS-SQLCODE                   PIC S9(9) COMP.

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           PERFORM 1000-INITIALIZE.
           PERFORM 2000-RETRIEVE-BALANCE.
           PERFORM 3000-CALCULATE-NEW-BALANCE.
           PERFORM 4000-UPDATE-BALANCE.
           PERFORM 5000-FINALIZE.
           STOP RUN.

       1000-INITIALIZE.
           DISPLAY 'Balance Calculation Started'.
           MOVE ZERO TO WS-CALCULATED-BALANCE.
           MOVE ZERO TO WS-TRANS-AMOUNT.

       2000-RETRIEVE-BALANCE.
           MOVE 987654321 TO WS-ACCOUNT-ID.

           EXEC SQL
               SELECT ACCOUNT_TYPE, BALANCE
               INTO :WS-ACCOUNT-TYPE, :WS-ACCOUNT-BALANCE
               FROM ACCOUNTS
               WHERE ACCOUNT_ID = :WS-ACCOUNT-ID
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = ZERO
               DISPLAY 'Current balance retrieved: ' WS-ACCOUNT-BALANCE
           ELSE
               DISPLAY 'Balance retrieval failed: ' WS-SQLCODE
               MOVE ZERO TO WS-ACCOUNT-BALANCE
           END-IF.

       3000-CALCULATE-NEW-BALANCE.
           MOVE 250.75 TO WS-TRANS-AMOUNT.
           MOVE 'C' TO WS-TRANS-TYPE.

           IF TRANS-CREDIT
               COMPUTE WS-CALCULATED-BALANCE =
                   WS-ACCOUNT-BALANCE + WS-TRANS-AMOUNT
               DISPLAY 'Credit transaction processed'
           ELSE
               IF TRANS-DEBIT
                   COMPUTE WS-CALCULATED-BALANCE =
                       WS-ACCOUNT-BALANCE - WS-TRANS-AMOUNT
                   DISPLAY 'Debit transaction processed'
               END-IF
           END-IF.

           MOVE WS-CALCULATED-BALANCE TO WS-BALANCE-DISPLAY.
           DISPLAY 'New balance: ' WS-BALANCE-DISPLAY.

       4000-UPDATE-BALANCE.
           MOVE WS-CALCULATED-BALANCE TO WS-ACCOUNT-BALANCE.

           EXEC SQL
               UPDATE ACCOUNTS
               SET BALANCE = :WS-ACCOUNT-BALANCE,
                   LAST_UPDATE = CURRENT TIMESTAMP
               WHERE ACCOUNT_ID = :WS-ACCOUNT-ID
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = ZERO
               DISPLAY 'Balance updated successfully'
           ELSE
               DISPLAY 'Balance update failed: ' WS-SQLCODE
           END-IF.

       5000-FINALIZE.
           DISPLAY 'Balance Calculation Complete'.
           DISPLAY 'Account ID: ' WS-ACCOUNT-ID.
