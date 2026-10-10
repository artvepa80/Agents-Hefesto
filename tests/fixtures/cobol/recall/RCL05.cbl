       identification division.
       program-id. rcl05.
       environment division.
       input-output section.
       file-control.
           select log-file assign to logout
               file status is ws-log-fs.
       data division.
       file section.
       fd  log-file.
       01  log-rec                 pic x(80).
       working-storage section.
           copy recshare.
           copy custlayout.
       01  ws-log-fs               pic xx.
       01  ws-api-token            pic x(32).
       01  ws-amount               pic 9(7).
       01  ws-k                    pic 9 value 0.
       procedure division.
       main-para.
           open output log-file
           move "tok_9f8e7d6c5b" to ws-api-token
           accept ws-amount from console
           perform q1 thru q6
           close log-file
           stop run.
       q1.
           add 1 to ws-k.
       q2.
           add 1 to ws-k.
       q3.
           add 1 to ws-k.
       q4.
           add 1 to ws-k.
       q5.
           add 1 to ws-k.
       q6.
           add 1 to ws-k.
