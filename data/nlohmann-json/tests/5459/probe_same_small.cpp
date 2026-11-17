// Hand-written probe: small integer vs float, same result either way.
#include <nlohmann/json.hpp>
#include <iostream>
int main() {
    nlohmann::json a = 3, b = 3.0, c = 4.5;
    std::cout << (a == b) << " " << (a < c) << "\n";
}
