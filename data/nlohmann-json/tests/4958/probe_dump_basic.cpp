// Hand-written probe: unaffected behavior, should be "same".
#include <nlohmann/json.hpp>
#include <iostream>
int main() {
    nlohmann::json j = {{"a", 1}, {"b", {1, 2, 3}}, {"c", "x"}};
    std::cout << j.dump() << "\n" << j["b"][1] << "\n";
}
