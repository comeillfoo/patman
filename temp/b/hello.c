#include <stdio.h>

void hello(const char* what)
{
    printf("Hello, %s\n", what);
}

int main(int argc, char** argv)
{
    hello("nothing");
    return 0;
}
