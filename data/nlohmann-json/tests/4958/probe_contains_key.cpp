// Hand-written probe: contains() with the same key type (regression fixed later by #5689; fails to compile on old and new here).
#include <nlohmann/json.hpp>
#include <iostream>
#include <string_view>
struct Key { operator std::string_view() const { return "k"; } };
int main() {
    nlohmann::json j = {{"k", 1}};
    std::cout << j.contains(Key{}) << "\n";
}
