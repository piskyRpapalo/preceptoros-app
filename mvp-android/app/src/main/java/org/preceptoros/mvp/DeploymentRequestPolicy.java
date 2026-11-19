package org.preceptoros.mvp;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.regex.Pattern;

/** Pure, review-only network contract. Never signs, admits, deploys or marks LIVE. */
public final class DeploymentRequestPolicy {
    public static final String ENDPOINT="https://api.preceptoros.org/api/v1/deployment-requests";
    public static final String SCHEMA="preceptoros.deployment-request/1";
    public static final String RECEIPT_SCHEMA="preceptoros.deployment-request-receipt/1";
    private static final Pattern NODE=Pattern.compile("^nodo\\.[0-9]{1,6}\\.[a-z0-9][a-z0-9-]{0,30}$");
    private static final Pattern HEX64=Pattern.compile("^[a-f0-9]{64}$");
    private static final Pattern NONCE=Pattern.compile("^[a-f0-9]{32}$");
    private DeploymentRequestPolicy(){}
    public static boolean validNode(String node){
        return node!=null&&NODE.matcher(node).matches();
    }
    public static boolean validPurpose(String purpose){
        if(purpose==null||purpose.trim().isEmpty()||purpose.length()>512)return false;
        for(int i=0;i<purpose.length();i++){
            char c=purpose.charAt(i);
            if(c<32||c==127)return false;
        }
        return true;
    }
    public static String buildBody(String node,String deviceDigest,String nonce){
        if(!validNode(node)||deviceDigest==null||!HEX64.matcher(deviceDigest).matches()||
            nonce==null||!NONCE.matcher(nonce).matches())throw new IllegalArgumentException("invalid_intake_identity");
        // ASCII-only canonical JSON, lexicographically ordered to match Aduana canonicalJson(obj,true).
        String result="{\"consent\":true,\"device_sha256\":\""+deviceDigest+"\",\"node\":\""+node+
                "\",\"nonce\":\""+nonce+"\",\"schema\":\""+SCHEMA+"\"}";
        if(result.getBytes(StandardCharsets.UTF_8).length>1024)throw new IllegalArgumentException("request_too_large");
        return result;
    }
    public static String sha256(String text){
        try{
            byte[] h=MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder out=new StringBuilder(64);
            for(byte b:h)out.append(String.format("%02x",b&0xff));
            return out.toString();
        }catch(Exception e){throw new IllegalStateException("digest_unavailable");}
    }
    public static boolean validReceipt(int status,String schema,String requestId,String state,
            String receivedAt,String authority,String credential,String live,String expectedHash){
        if(status!=200&&status!=202)return false;
        if(!RECEIPT_SCHEMA.equals(schema)||expectedHash==null||!HEX64.matcher(expectedHash).matches())return false;
        if(!expectedHash.equals(requestId)||!"AWAITING_HUMAN".equals(state)||
            !"NONE".equals(authority)||!"NOT_PROVISIONED".equals(credential)||
            !"NO_DATA(heartbeat_not_verified)".equals(live))return false;
        if(receivedAt==null||receivedAt.length()>40||!receivedAt.endsWith("Z"))return false;
        try{Instant.parse(receivedAt);}catch(Exception error){return false;}
        return true;
    }
    public static boolean validNotification(String notification){
        return "QUEUED".equals(notification)||"SENDING".equals(notification)||"DELIVERED".equals(notification);
    }
}
