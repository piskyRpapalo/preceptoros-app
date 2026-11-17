// PreceptorOS MINI-LOCAL: local text inference only; no tools, network or rack access.
#include <jni.h>
#include <algorithm>
#include <mutex>
#include <string>
#include <vector>
#include "llama.h"

namespace {
std::mutex mx;
llama_model * loaded_model = nullptr;
std::string loaded_path;
bool backend_ready = false;
std::string no_data(const char *cause) { return std::string("NO_DATA(") + cause + ")"; }

std::string infer(const std::string &path, const std::string &user) {
    std::lock_guard<std::mutex> lk(mx);
    if (path.empty() || user.empty() || user.size() > 640) return no_data("mini_input_invalid");
    if (!backend_ready) { llama_backend_init(); backend_ready = true; }
    if (!loaded_model || loaded_path != path) {
        if (loaded_model) { llama_model_free(loaded_model); loaded_model = nullptr; }
        llama_model_params mp = llama_model_default_params();
        loaded_model = llama_model_load_from_file(path.c_str(), mp);
        if (!loaded_model) return no_data("mini_model_load_failed");
        loaded_path = path;
    }
    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = 512; cp.n_batch = 384; cp.n_ubatch = 384;
    cp.n_threads = 4; cp.n_threads_batch = 4;
    llama_context *ctx = llama_init_from_model(loaded_model, cp);
    if (!ctx) return no_data("mini_context_init_failed");
    const llama_vocab *vocab = llama_model_get_vocab(loaded_model);
    if (!vocab) { llama_free(ctx); return no_data("mini_vocab_missing"); }
    const std::string prompt =
        "<|im_start|>system\nYou are MINI-LOCAL, a small offline PreceptorOS assistant. "
        "Answer briefly in the user's language. Do not claim internet, access to the rack, "
        "running tools, reading local files, or authorization. Say when unsure.\n<|im_end|>\n"
        "<|im_start|>user\n" + user + "\n<|im_end|>\n<|im_start|>assistant\n";
    std::vector<llama_token> tokens(384);
    int n = llama_tokenize(vocab, prompt.c_str(), (int) prompt.size(),
                           tokens.data(), (int) tokens.size(), true, true);
    if (n <= 0 || n > 384) { llama_free(ctx); return no_data("mini_tokenize_failed"); }
    llama_batch_ext *batch = llama_batch_ext_init(ctx);
    if (!batch) { llama_free(ctx); return no_data("mini_batch_init_failed"); }
    bool valid = true;
    for (int i=0; i<n; ++i) {
        int idx = llama_batch_ext_add_token(batch, 0, tokens[i]);
        llama_pos pos = i;
        if (idx < 0 || !llama_batch_ext_set_pos(batch, idx, &pos) ||
            !llama_batch_ext_set_output_logits(batch, idx, i == n-1)) {
            valid = false; break;
        }
    }
    if (!valid || llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE, batch) != 0) {
        llama_batch_ext_free(batch); llama_free(ctx);
        return no_data("mini_prompt_process_failed");
    }
    std::string out;
    const int32_t count = llama_vocab_n_tokens(vocab);
    for (int step = 0; step < 72 && n+step < 510; ++step) {
        float *logits = llama_get_logits_ith(ctx, -1);
        if (!logits) { out = no_data("mini_missing_logits"); break; }
        llama_token pick = 0;
        for (llama_token t=1; t<count; ++t)
            if (logits[t] > logits[pick]) pick=t;
        if (llama_vocab_is_eog(vocab,pick)) break;
        char bytes[512] = {};
        int used = llama_token_to_piece(vocab,pick,bytes,sizeof(bytes),0,false);
        if (used > 0 && used < (int)sizeof(bytes) && out.size()+used < 4000)
            out.append(bytes,used);
        llama_batch_ext_clear(batch);
        int idx = llama_batch_ext_add_token(batch,0,pick);
        llama_pos pos = n+step;
        if (idx<0 || !llama_batch_ext_set_pos(batch,idx,&pos) ||
            !llama_batch_ext_set_output_logits(batch,idx,true) ||
            llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE,batch)!=0) {
            out = no_data("mini_generation_failed"); break;
        }
    }
    llama_batch_ext_free(batch); llama_free(ctx);
    return out.empty() ? no_data("mini_empty_generation") : out;
}
}
extern "C" JNIEXPORT jstring JNICALL
Java_org_preceptoros_mvp_MiniNative_generate(JNIEnv *env, jclass, jstring jpath, jstring jprompt) {
    if (!jpath || !jprompt) return env->NewStringUTF("NO_DATA(mini_null_input)");
    const char *p=env->GetStringUTFChars(jpath,nullptr);
    const char *q=env->GetStringUTFChars(jprompt,nullptr);
    if (!p || !q) {
        if (p) env->ReleaseStringUTFChars(jpath,p);
        if (q) env->ReleaseStringUTFChars(jprompt,q);
        return env->NewStringUTF("NO_DATA(mini_utf8_error)");
    }
    std::string out=infer(p,q);
    env->ReleaseStringUTFChars(jpath,p);
    env->ReleaseStringUTFChars(jprompt,q);
    return env->NewStringUTF(out.c_str());
}
