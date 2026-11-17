package org.preceptoros.mvp;

/** Native text generation: optional and strictly on-device. No network or commands. */
final class MiniNative {
    private static final boolean loaded;
    static {
        boolean ok = false;
        try { System.loadLibrary("mini_llama"); ok = true; }
        catch (UnsatisfiedLinkError unavailable) { /* NO_DATA until a verified native build is bundled. */ }
        loaded = ok;
    }
    static boolean available() { return loaded; }
    static native String generate(String verifiedModelPath, String userPrompt);
    private MiniNative() {}
}
