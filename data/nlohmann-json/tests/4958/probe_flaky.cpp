// Hand-written probe: nondeterministic output, should be "flaky".
#include <iostream>
#include <random>
int main() { std::random_device rd; std::cout << rd() << "\n"; }
