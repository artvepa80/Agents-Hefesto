      *****************************************************************
      * Purpose: Batch DB2 program with hardcoded credentials
      * Rules: HARDCODED_CREDENTIALS (positive test)
      * Expected: 2 CRITICAL findings (lines ~35, ~45)
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BATCH-DB2.
       AUTHOR. LEGACY-TEAM.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DB-CONNECTION.
           05  WS-DB-USER               PIC X(20).
           05  WS-DB-PASSWORD           PIC X(30).
           05  WS-DB-HOST               PIC X(50).
           05  WS-DB-PORT               PIC 9(5).

       01  WS-API-CONFIG.
           05  WS-API-ENDPOINT          PIC X(100).
           05  WS-API-KEY               PIC X(40).
           05  WS-API-SECRET            PIC X(40).

       01  WS-SQLCODE                   PIC S9(9) COMP.
       01  WS-RECORD-COUNT              PIC 9(7) VALUE ZERO.
       01  WS-BATCH-STATUS              PIC X(10).

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           PERFORM 1000-SETUP-CONNECTION.
           PERFORM 2000-PROCESS-BATCH.
           PERFORM 3000-CLEANUP.
           STOP RUN.

       1000-SETUP-CONNECTION.
           DISPLAY 'Setting up database connection...'.
           MOVE 'DB2ADMIN' TO WS-DB-USER.
      * CRITICAL: Hardcoded password (line ~35)
           MOVE 'PROD2026!' TO WS-DB-PASSWORD.
           MOVE 'db2.production.local' TO WS-DB-HOST.
           MOVE 50000 TO WS-DB-PORT.

           DISPLAY 'Configuring API access...'.
           MOVE 'https://api.internal.corp/v1' TO WS-API-ENDPOINT.
      * CRITICAL: Hardcoded API key (line ~45)
           MOVE 'sk-prod-a1b2c3d4e5f6g7h8i9j0' TO WS-API-KEY.
           MOVE 'secret-xyzabc123def456' TO WS-API-SECRET.

           EXEC SQL
               CONNECT TO PRODUCTION
               USER :WS-DB-USER
               USING :WS-DB-PASSWORD
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE NOT = ZERO
               DISPLAY 'Connection failed: ' WS-SQLCODE
               MOVE 'FAILED' TO WS-BATCH-STATUS
           ELSE
               DISPLAY 'Connected to DB2 successfully'
               MOVE 'ACTIVE' TO WS-BATCH-STATUS
           END-IF.

       2000-PROCESS-BATCH.
           IF WS-BATCH-STATUS = 'ACTIVE'
               PERFORM 2100-SELECT-RECORDS
               PERFORM 2200-UPDATE-RECORDS
           ELSE
               DISPLAY 'Skipping batch - connection failed'
           END-IF.

       2100-SELECT-RECORDS.
           EXEC SQL
               SELECT COUNT(*)
               INTO :WS-RECORD-COUNT
               FROM BATCH_QUEUE
               WHERE STATUS = 'PENDING'
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = ZERO
               DISPLAY 'Records to process: ' WS-RECORD-COUNT
           ELSE
               DISPLAY 'Query failed: ' WS-SQLCODE
           END-IF.

       2200-UPDATE-RECORDS.
           EXEC SQL
               UPDATE BATCH_QUEUE
               SET STATUS = 'PROCESSED',
                   PROCESSED_DATE = CURRENT TIMESTAMP
               WHERE STATUS = 'PENDING'
           END-EXEC.

           MOVE SQLCODE TO WS-SQLCODE.
           IF WS-SQLCODE = ZERO
               DISPLAY 'Records updated successfully'
           ELSE
               DISPLAY 'Update failed: ' WS-SQLCODE
           END-IF.

       3000-CLEANUP.
           EXEC SQL
               COMMIT WORK
           END-EXEC.

           EXEC SQL
               DISCONNECT CURRENT
           END-EXEC.

           DISPLAY 'Batch process complete.'.
           DISPLAY 'Status: ' WS-BATCH-STATUS.
