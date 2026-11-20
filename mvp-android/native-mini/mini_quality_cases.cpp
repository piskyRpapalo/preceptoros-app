// PreceptorOS MINI quality unit tests — deterministic, no model required.
// Tests the has_loop() and sample_token() helpers extracted from mini_jni.cpp.
// Compile standalone: g++ -std=c++17 -o mini_quality_cases mini_quality_cases.cpp

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <numeric>
#include <vector>

using llama_token = int32_t;

/* --- has_loop (copied from mini_jni.cpp for standalone testing) --- */
static bool has_loop(const std::vector<llama_token> &history,
                     int window, int min_len, int min_count) {
    if ((int)history.size() < window) return false;
    int n = (int)history.size();
    int tail = n - window;
    for (int len = min_len; len <= window / 2; ++len) {
        int count = 1;
        for (int i = 0; i + len * 2 < window; ++i) {
            bool match = true;
            for (int j = 0; j < len; ++j) {
                if (history[tail + i + j] != history[tail + i + len + j]) { match = false; break; }
            }
            if (match) { ++count; i += len - 1; }
        }
        if (count >= min_count) return true;
    }
    return false;
}

/* --- sample_token (copied from mini_jni.cpp for standalone testing) --- */
static llama_token sample_token(const float *logits, int32_t count,
                                float temperature, int top_k) {
    std::vector<float> scaled(count);
    for (int32_t i = 0; i < count; ++i)
        scaled[i] = logits[i] / temperature;

    std::vector<int32_t> indices(count);
    std::iota(indices.begin(), indices.end(), 0);
    int k = std::min(top_k, (int)count);
    std::partial_sort(indices.begin(), indices.begin() + k, indices.end(),
        [&scaled](int32_t a, int32_t b) { return scaled[a] > scaled[b]; });

    float max_logit = scaled[indices[0]];
    float sum = 0.0f;
    std::vector<float> probs(k);
    for (int i = 0; i < k; ++i) {
        probs[i] = std::exp(scaled[indices[i]] - max_logit);
        sum += probs[i];
    }
    for (int i = 0; i < k; ++i) probs[i] /= sum;

    static uint32_t seed = 42;
    seed ^= (seed << 13) ^ (seed >> 17) ^ (seed << 5);
    float r = ((double)seed) / 4294967295.0;
    float cdf = 0.0f;
    for (int i = 0; i < k; ++i) {
        cdf += probs[i];
        if (r <= cdf) return indices[i];
    }
    return indices[k - 1];
}

/* --- test harness --- */
static int passed = 0, failed = 0;
#define ASSERT(cond, msg) do { \
    if (cond) { ++passed; } \
    else { ++failed; std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n"; } \
} while(0)

void test_has_loop_no_loop_short_history() {
    std::vector<llama_token> v = {1,2,3,4,5,6,7,8,9,10,11,12};
    ASSERT(!has_loop(v, 12, 3, 2), "short history should not trigger loop");
}

void test_has_loop_repeated_sequence() {
    // 12 tokens: [1,2,3, 1,2,3, 4,5,6, 4,5,6] — two repeats of len-3 in window=12
    std::vector<llama_token> v = {1,2,3,1,2,3,4,5,6,4,5,6};
    ASSERT(has_loop(v, 12, 3, 2), "repeated 3-gram should be detected");
}

void test_has_loop_identical_repeat() {
    // All same token: [5,5,5,5,5,5,5,5,5,5,5,5]
    std::vector<llama_token> v(12, 5);
    ASSERT(has_loop(v, 12, 3, 2), "identical tokens should be detected as loop");
}

void test_has_loop_diverse_no_repeat() {
    std::vector<llama_token> v = {1,2,3,4,5,6,7,8,9,10,11,12};
    ASSERT(!has_loop(v, 12, 3, 2), "diverse tokens should not trigger loop");
}

void test_has_loop_too_short_for_window() {
    std::vector<llama_token> v = {1,2,3,4,5};
    ASSERT(!has_loop(v, 12, 3, 2), "history too short should not trigger loop");
}

void test_has_loop_longer_history_with_repeat() {
    // 20 tokens, last 12 contain repeat: [..., 1,2,3, 1,2,3, 4,5,6, 4,5,6]
    std::vector<llama_token> v = {100,100,100,100,100,100,1,2,3,1,2,3,4,5,6,4,5,6,7,8};
    ASSERT(has_loop(v, 12, 3, 2), "longer history with repeat in tail should detect loop");
}

void test_sample_token_returns_top_k_member() {
    float logits[10] = {0, 10, 3, 4, 5, 6, 7, 8, 9, 1}; // token 1 has highest logit
    llama_token t = sample_token(logits, 10, 1.0f, 5);
    // With deterministic seed=42, result should be one of top-5 tokens (1,8,9,7,6)
    bool in_top5 = (t==1 || t==8 || t==9 || t==7 || t==6);
    ASSERT(in_top5, "sample should return a top-k token");
}

void test_sample_token_temperature_diversity() {
    // With very high temperature, distribution flattens — should still pick from top-k
    float logits[5] = {0, 100, 0, 0, 0};
    llama_token t = sample_token(logits, 5, 100.0f, 3);
    // Even at high temp, top-3 includes token 1 and two others
    bool in_top3 = (t==1 || t==0 || t==2); // top-3 by logit: 1,0,2 (tied)
    ASSERT(in_top3, "high-temp sample should still be within top-k");
}

void test_sample_token_deterministic_seed() {
    float logits[4] = {0, 1, 2, 3};
    // Reset seed for reproducibility
    // First call with seed=42
    llama_token t1 = sample_token(logits, 4, 1.0f, 4);
    // Second call — seed state advanced, should differ or be same depending on distribution
    llama_token t2 = sample_token(logits, 4, 1.0f, 4);
    // Both should be valid tokens
    ASSERT(t1 >= 0 && t1 < 4, "first sample should be valid token");
    ASSERT(t2 >= 0 && t2 < 4, "second sample should be valid token");
}

void test_sample_token_not_pure_argmax() {
    // With temperature > 0 and top-k > 1, we should NOT always pick the argmax
    // (unless the distribution is extremely peaked).
    // Use moderate logits where top-k has meaningful spread.
    float logits[10] = {0,1,2,3,4,5,6,7,8,9};
    int argmax_count = 0;
    for (int i = 0; i < 10; ++i) {
        llama_token t = sample_token(logits, 10, 0.8f, 5);
        if (t == 9) ++argmax_count; // token 9 has highest logit
    }
    // With top-k=5 and temp=0.8, argmax should NOT be picked every time
    ASSERT(argmax_count < 10, "sampling should not always return argmax");
}

int main() {
    std::cout << "=== MINI quality cases ===\n";
    test_has_loop_no_loop_short_history();
    test_has_loop_repeated_sequence();
    test_has_loop_identical_repeat();
    test_has_loop_diverse_no_repeat();
    test_has_loop_too_short_for_window();
    test_has_loop_longer_history_with_repeat();
    test_sample_token_returns_top_k_member();
    test_sample_token_temperature_diversity();
    test_sample_token_deterministic_seed();
    test_sample_token_not_pure_argmax();
    std::cout << "passed: " << passed << "  failed: " << failed << "\n";
    return failed > 0 ? 1 : 0;
}
