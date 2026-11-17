// Hand-written probe for #4958: a string_view-convertible key type used with operator[].
#include <nlohmann/json.hpp>
#include <iostream>
#include <string_view>
struct Key { operator std::string_view() const { return "k"; } };
int main() {
    nlohmann::json j = {{"k", 1}};
    std::cout << j[Key{}] << "\n";
}
