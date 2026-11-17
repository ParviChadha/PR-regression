// Hand-written probe: never terminates, should be "invalid" (times out on both).
int main() { volatile int x = 0; for (;;) x = x + 1; }
