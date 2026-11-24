package org.preceptoros.mvp;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Owner-approved credential persistence: ciphertext only, with a device Keystore key. */
final class HeartbeatCredentialStore {
    private static final String PREFS = "preceptoros.heartbeat.service";
    private static final String ALIAS = "preceptoros.heartbeat.service.aes-gcm.v1";
    private static final String ANDROID_KEYSTORE = "AndroidKeyStore";
    private static final String CIPHERTEXT = "credential_ciphertext";
    private static final String IV = "credential_iv";

    static final class Credential {
        final String node;
        final String key;
        Credential(String node, String key) { this.node = node; this.key = key; }
    }

    private HeartbeatCredentialStore() {}

    static void save(Context context, String node, String key, boolean autoResume) throws Exception {
        if (!HeartbeatOncePolicy.node(node) || !HeartbeatOncePolicy.key(key))
            throw new IllegalArgumentException("credential_shape_invalid");
        JSONObject value = new JSONObject();
        value.put("schema", HeartbeatOncePolicy.KEY_FILE);
        value.put("node", node);
        value.put("key", key);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, encryptionKey(true));
        byte[] ciphertext = cipher.doFinal(value.toString().getBytes(StandardCharsets.UTF_8));
        SharedPreferences.Editor editor = prefs(context).edit()
                .putString(IV, Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString(CIPHERTEXT, Base64.encodeToString(ciphertext, Base64.NO_WRAP))
                .putBoolean("consent_active", true)
                .putBoolean("auto_resume", autoResume);
        if (!editor.commit()) throw new IllegalStateException("credential_storage_unavailable");
    }

    /**
     * Consent for the node born on THIS phone (NodeOwner): no credential copy is stored, because its heartbeat key,
     * renewal and sequence already live in NodeOwner's private state. Revocation stops the beats and clears consent;
     * it does not delete the node's identity (that would need a new admission).
     */
    static void saveDeviceNode(Context context, String alias, boolean autoResume) {
        if (alias == null || !NodeOwner.ALIAS.matcher(alias).matches())
            throw new IllegalArgumentException("device_node_alias_invalid");
        SharedPreferences.Editor editor = prefs(context).edit().clear()
                .putString("source", "device_node")
                .putString("device_alias", alias)
                .putBoolean("consent_active", true)
                .putBoolean("auto_resume", autoResume);
        if (!editor.commit()) throw new IllegalStateException("credential_storage_unavailable");
    }

    static boolean deviceNode(Context context) {
        return consentActive(context) && "device_node".equals(prefs(context).getString("source", null));
    }

    static String deviceAlias(Context context) {
        return deviceNode(context) ? prefs(context).getString("device_alias", null) : null;
    }

    static boolean consentActive(Context context) {
        return prefs(context).getBoolean("consent_active", false);
    }

    static boolean autoResume(Context context) {
        return consentActive(context) && prefs(context).getBoolean("auto_resume", false);
    }

    static Credential load(Context context) throws Exception {
        SharedPreferences preferences = prefs(context);
        if (!preferences.getBoolean("consent_active", false)) return null;
        String ivText = preferences.getString(IV, null);
        String encryptedText = preferences.getString(CIPHERTEXT, null);
        if (ivText == null || encryptedText == null) return null;
        byte[] iv = Base64.decode(ivText, Base64.NO_WRAP);
        byte[] encrypted = Base64.decode(encryptedText, Base64.NO_WRAP);
        if (iv.length != 12 || encrypted.length < 17 || encrypted.length > 1024)
            throw new IllegalStateException("credential_ciphertext_invalid");
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, encryptionKey(false), new GCMParameterSpec(128, iv));
        JSONObject value = new JSONObject(new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8));
        if (value.length() != 3 || !HeartbeatOncePolicy.KEY_FILE.equals(value.optString("schema")) ||
                !HeartbeatOncePolicy.node(value.optString("node")) ||
                !HeartbeatOncePolicy.key(value.optString("key")))
            throw new IllegalStateException("credential_plaintext_invalid");
        return new Credential(value.getString("node"), value.getString("key"));
    }

    /** Revocation removes the stored ciphertext and makes its Keystore key unusable. */
    static boolean revoke(Context context) {
        boolean cleared = prefs(context).edit().clear().commit();
        try {
            KeyStore store = KeyStore.getInstance(ANDROID_KEYSTORE);
            store.load(null);
            if (store.containsAlias(ALIAS)) store.deleteEntry(ALIAS);
            return cleared;
        } catch (Exception failure) {
            return false;
        }
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static SecretKey encryptionKey(boolean create) throws Exception {
        KeyStore store = KeyStore.getInstance(ANDROID_KEYSTORE);
        store.load(null);
        if (store.containsAlias(ALIAS)) return (SecretKey) store.getKey(ALIAS, null);
        if (!create) throw new IllegalStateException("credential_keystore_key_missing");
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE);
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .setKeySize(256)
                .build());
        return generator.generateKey();
    }
}
