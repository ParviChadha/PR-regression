// Hand-written probe for #5459: integer vs float comparison (old widened the integer to double).
#include <nlohmann/json.hpp>
#include <iostream>
int main() {
    nlohmann::json a = 9007199254740993LL, b = 9007199254740992.0;
    std::cout << (a == b) << " " << (a < b) << " " << (a > b) << "\n";
}
