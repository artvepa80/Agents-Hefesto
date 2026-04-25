      *****************************************************************
      * Purpose: Legacy report program with multiple security issues
      * Rules: HARDCODED_CREDENTIALS, GOTO_EXCESSIVE, ACCEPT (mixed)
      * Expected: 3 findings
      *   - 1 CRITICAL (hardcoded password, line ~46)
      *   - 1 HIGH (>10 GO TOs throughout)
      *   - 1 MEDIUM (ACCEPT unvalidated, line ~62)
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LEGACY-REPORT.
       AUTHOR. LEGACY-TEAM.
       DATE-WRITTEN. 1998-03-15.
       DATE-COMPILED. 2026-04-25.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-370.
       OBJECT-COMPUTER. IBM-370.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REPORT-CONFIG.
           05  WS-REPORT-TYPE           PIC X(20).
           05  WS-OUTPUT-FORMAT         PIC X(10).
           05  WS-DATE-RANGE-START      PIC X(10).
           05  WS-DATE-RANGE-END        PIC X(10).

       01  WS-DB-CONFIG.
           05  WS-DB-SERVER             PIC X(50).
           05  WS-DB-USER               PIC X(20).
           05  WS-DB-PASSWORD           PIC X(30).
           05  WS-DB-DATABASE           PIC X(30).

       01  WS-USER-INPUT                PIC X(50).
       01  WS-REPORT-COUNT              PIC 9(7) VALUE ZERO.
       01  WS-ERROR-FLAG                PIC X VALUE 'N'.
       01  WS-STATUS-CODE               PIC X(2).
       01  WS-RETRY-COUNT               PIC 9(2) VALUE ZERO.

       PROCEDURE DIVISION.
       START-PROGRAM.
           DISPLAY 'Legacy Report Generator v1.5'.
           GO TO SETUP-CONNECTION.

       SETUP-CONNECTION.
           MOVE 'reports.legacy.corp' TO WS-DB-SERVER.
           MOVE 'REPORTUSER' TO WS-DB-USER.
      * CRITICAL: Hardcoded password (line ~46)
           MOVE 'Report#2026' TO WS-DB-PASSWORD.
           MOVE 'REPORTS_DB' TO WS-DB-DATABASE.
           DISPLAY 'Database configured'.
           GO TO GET-USER-PARAMS.

       GET-USER-PARAMS.
           DISPLAY 'Enter report type (DAILY/WEEKLY/MONTHLY): '.
      * MEDIUM: ACCEPT without validation (line ~62)
           ACCEPT WS-REPORT-TYPE.
           DISPLAY 'Enter output format (PDF/CSV/TXT): '.
           ACCEPT WS-OUTPUT-FORMAT.
           DISPLAY 'Parameters accepted'.
           GO TO VALIDATE-PARAMS.

       VALIDATE-PARAMS.
           IF WS-REPORT-TYPE = 'DAILY'
               GO TO CHECK-FORMAT
           ELSE
               IF WS-REPORT-TYPE = 'WEEKLY'
                   GO TO CHECK-FORMAT
               ELSE
                   IF WS-REPORT-TYPE = 'MONTHLY'
                       GO TO CHECK-FORMAT
                   ELSE
                       DISPLAY 'Invalid report type'.
                       GO TO ERROR-RECOVERY
                   END-IF
               END-IF
           END-IF.

       CHECK-FORMAT.
           IF WS-OUTPUT-FORMAT = 'PDF'
               GO TO GENERATE-REPORT
           ELSE
               IF WS-OUTPUT-FORMAT = 'CSV'
                   GO TO GENERATE-REPORT
               ELSE
                   IF WS-OUTPUT-FORMAT = 'TXT'
                       GO TO GENERATE-REPORT
                   ELSE
                       DISPLAY 'Invalid format'.
                       GO TO ERROR-RECOVERY
                   END-IF
               END-IF
           END-IF.

       GENERATE-REPORT.
           DISPLAY 'Generating report...'.
           DISPLAY 'Type: ' WS-REPORT-TYPE.
           DISPLAY 'Format: ' WS-OUTPUT-FORMAT.
           ADD 1 TO WS-REPORT-COUNT.
           MOVE '00' TO WS-STATUS-CODE.
           IF WS-STATUS-CODE = '00'
               GO TO WRITE-REPORT
           ELSE
               GO TO ERROR-RECOVERY
           END-IF.

       WRITE-REPORT.
           DISPLAY 'Writing report to disk...'.
           IF WS-OUTPUT-FORMAT = 'PDF'
               DISPLAY 'PDF written successfully'
               GO TO SEND-EMAIL
           ELSE
               DISPLAY 'Report written successfully'
               GO TO SEND-EMAIL
           END-IF.

       SEND-EMAIL.
           DISPLAY 'Sending email notification...'.
           MOVE '00' TO WS-STATUS-CODE.
           IF WS-STATUS-CODE = '00'
               DISPLAY 'Email sent'
               GO TO CLEANUP
           ELSE
               DISPLAY 'Email failed'
               GO TO ERROR-RECOVERY
           END-IF.

       ERROR-RECOVERY.
           MOVE 'Y' TO WS-ERROR-FLAG.
           ADD 1 TO WS-RETRY-COUNT.
           IF WS-RETRY-COUNT > 3
               DISPLAY 'Max retries exceeded'.
               GO TO ABORT-PROGRAM
           ELSE
               DISPLAY 'Retrying operation...'.
               MOVE ZERO TO WS-RETRY-COUNT.
               GO TO GET-USER-PARAMS
           END-IF.

       CLEANUP.
           DISPLAY 'Cleaning up resources...'.
           DISPLAY 'Reports generated: ' WS-REPORT-COUNT.
           IF WS-ERROR-FLAG = 'N'
               GO TO END-PROGRAM
           ELSE
               DISPLAY 'Completed with errors'.
               GO TO END-PROGRAM
           END-IF.

       ABORT-PROGRAM.
           DISPLAY 'Program aborted due to errors.'.
           GO TO END-PROGRAM.

       END-PROGRAM.
           DISPLAY 'Legacy Report Generator terminated.'.
           STOP RUN.
