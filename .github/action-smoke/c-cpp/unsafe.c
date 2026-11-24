/* Action smoke fixture: gets() must be reported as CC001 (HIGH). */
#include <stdio.h>

int read_line(void)
{
    char buf[64];
    gets(buf);
    return buf[0];
}
