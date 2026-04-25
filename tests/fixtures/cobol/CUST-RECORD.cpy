      *****************************************************************
      * Purpose: Customer record copybook (shared data structure)
      * Rules: COPYBOOK_BLAST_RADIUS (referenced by multiple programs)
      * Expected: 0 findings from copybook itself (data definition)
      * Note: REDEFINES_SENSITIVE will be detected when analyzing
      *       programs that COPY this (line ~18)
      *****************************************************************
       01  CUSTOMER-RECORD.
           05  CUST-ID                  PIC 9(9).
           05  CUST-NAME                PIC X(50).
           05  CUST-ADDRESS.
               10  CUST-STREET          PIC X(40).
               10  CUST-CITY            PIC X(30).
               10  CUST-STATE           PIC X(2).
               10  CUST-ZIP             PIC 9(5).
           05  CUST-PHONE               PIC X(15).
           05  CUST-EMAIL               PIC X(50).
           05  CUST-ACCOUNT-BALANCE     PIC S9(11)V99 COMP-3.
      * This REDEFINES will be flagged when programs COPY this
           05  CUST-BALANCE-RAW REDEFINES CUST-ACCOUNT-BALANCE
                                        PIC X(8).
           05  CUST-CREDIT-LIMIT        PIC S9(9)V99 COMP-3.
           05  CUST-STATUS              PIC X(10).
           05  CUST-CREATED-DATE        PIC X(10).
           05  CUST-LAST-ACTIVITY       PIC X(10).
