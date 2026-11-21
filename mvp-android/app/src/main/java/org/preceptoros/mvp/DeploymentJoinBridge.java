package org.preceptoros.mvp;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.net.Uri;
import android.webkit.WebView;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import androidx.webkit.JavaScriptReplyProxy;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import javax.net.ssl.HttpsURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Owner-controlled HTTPS review request, never node admission.
 * Unlike addJavascriptInterface, the message listener verifies origin + main frame.
 * Fail closed when the WebView provider cannot enforce the origin rule.
 */
final class DeploymentJoinBridge {
    private static final String EXPECTED_ORIGIN=OwnerFrameAccess.ORIGIN;
    private static final int MAX_REPLY_BYTES=3072;
    private final MainActivity activity;
    private final AtomicBoolean busy=new AtomicBoolean(false);
    private final SecureRandom random=new SecureRandom();

    private DeploymentJoinBridge(MainActivity activity){this.activity=activity;}
    static boolean install(MainActivity activity,WebView web){
        if(!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER))return false;
        DeploymentJoinBridge bridge=new DeploymentJoinBridge(activity);
        WebViewCompat.addWebMessageListener(web,"PreceptorJoinNative",
            Collections.singleton(EXPECTED_ORIGIN),
            (view,message,origin,isMainFrame,reply)->{
                if(!OwnerFrameAccess.accepts(origin == null ? null : origin.toString(),
                    isMainFrame, activity.ownPageVerified(), view.getUrl())){
                    bridge.reply(reply,"",false,"origin_or_page_unverified",null);return;
                }
                String payload=message.getData();
                if(payload==null||payload.length()>1100){
                    bridge.reply(reply,"",false,"message_out_of_range",null);return;
                }
                activity.runOnUiThread(()->bridge.review(payload,reply));
            });
        return true;
    }
    private void reply(JavaScriptReplyProxy target,String id,boolean ok,String cause,JSONObject result){
        try{
            JSONObject out=new JSONObject();
            out.put("id",id);out.put("ok",ok);
            if(!ok)out.put("cause",cause);
            if(ok&&result!=null)out.put("result",result);
            activity.runOnUiThread(()->target.postMessage(out.toString()));
        }catch(Exception ignored){/* No false success; frontend has a bounded timeout. */}
    }
    private static boolean exact(JSONObject o,String... fields){
        if(o==null||o.length()!=fields.length)return false;
        for(String f:fields)if(!o.has(f))return false;
        return true;
    }
    private void review(String raw,JavaScriptReplyProxy reply){
        String id="";
        try{
            JSONObject request=new JSONObject(raw);
            id=request.optString("id","");
            if(!id.matches("[a-f0-9]{32}")||
                !exact(request,"id","node","purpose","consent")||
                !request.optBoolean("consent",false)){
                reply(reply,id,false,"invalid_or_unconsented_message",null);return;
            }
            String node=request.optString("node",""),purpose=request.optString("purpose","");
            if(!DeploymentRequestPolicy.validNode(node)||
                !DeploymentRequestPolicy.validPurpose(purpose)){
                reply(reply,id,false,"invalid_node_or_purpose",null);return;
            }
            if(!busy.compareAndSet(false,true)){
                reply(reply,id,false,"request_in_flight",null);return;
            }
            final String correlation=id;
            // Second, native consent is always necessary; JS alone cannot send.
            new AlertDialog.Builder(activity)
                .setTitle("Send a node review request?")
                .setMessage("Proposed node: "+node+"\n\nThis sends an installation-scoped pseudonymous digest "+
                    "to api.preceptoros.org for human review. Purpose remains on this device until "+
                    "the server contract supports it. This does not deploy a node, approve it, "+
                    "publish data or grant tools.")
                .setNegativeButton("Cancel",(dlg,which)->{
                    busy.set(false);reply(reply,correlation,false,"owner_cancelled",null);
                })
                .setOnCancelListener(dlg->{
                    busy.set(false);reply(reply,correlation,false,"owner_cancelled",null);
                })
                .setPositiveButton("Send review request",(dlg,which)->{
                    if(!activity.ownPageVerified()){
                        busy.set(false);reply(reply,correlation,false,"page_not_verified",null);return;
                    }
                    new Thread(()->{
                        try{
                            String body=bodyFor(node,purpose);
                            String hash=DeploymentRequestPolicy.sha256(body);
                            JSONObject result=sendToFixedEndpoint(body,hash,node);
                            reply(reply,correlation,true,null,result);
                        }catch(Exception error){
                            reply(reply,correlation,false,normalize(error),null);
                        }finally{busy.set(false);}
                    },"preceptoros-owner-intake").start();
                }).show();
        }catch(Exception malformed){reply(reply,id,false,"invalid_json_request",null);}
    }
    private String randomHex(int bytes){
        byte[] b=new byte[bytes];random.nextBytes(b);
        StringBuilder out=new StringBuilder(bytes*2);
        final char[] hex="0123456789abcdef".toCharArray();
        for(byte x:b){out.append(hex[(x>>>4)&15]).append(hex[x&15]);}
        return out.toString();
    }
    private String bodyFor(String node,String purpose){
        SharedPreferences prefs=activity.getSharedPreferences("preceptoros.join.install",Activity.MODE_PRIVATE);
        String seed=prefs.getString("installation_seed",null);
        if(seed==null||!seed.matches("[a-f0-9]{64}")){
            seed=randomHex(32);
            if(!prefs.edit().putString("installation_seed",seed).commit())
                throw new IllegalStateException("local_identity_storage_unavailable");
        }
        String deviceDigest=DeploymentRequestPolicy.sha256(seed);
        String purposeHash=DeploymentRequestPolicy.sha256(purpose);
        String cached=prefs.getString("pending_body",null);
        String pendingNode=prefs.getString("pending_node",null);
        String pendingPurpose=prefs.getString("pending_purpose_hash",null);
        if(node.equals(pendingNode)&&purposeHash.equals(pendingPurpose)&&cached!=null){
            try{
                JSONObject old=new JSONObject(cached);
                if(exact(old,"schema","node","device_sha256","nonce","consent")&&
                    DeploymentRequestPolicy.SCHEMA.equals(old.optString("schema"))&&
                    node.equals(old.optString("node"))&&deviceDigest.equals(old.optString("device_sha256"))&&
                    old.optBoolean("consent")&&cached.length()<1024){
                    String checked=DeploymentRequestPolicy.buildBody(node,deviceDigest,old.optString("nonce"));
                    if(cached.equals(checked))return cached;
                }
            }catch(Exception ignored){/* Reject tampered cache, generate a fresh nonce. */}
        }
        String body=DeploymentRequestPolicy.buildBody(node,deviceDigest,randomHex(16));
        if(!prefs.edit().putString("pending_node",node).putString("pending_purpose_hash",purposeHash)
            .putString("pending_body",body).commit())
            throw new IllegalStateException("local_pending_storage_unavailable");
        return body;
    }
    private JSONObject sendToFixedEndpoint(String body,String expectedHash,String node)throws Exception{
        URL url=new URL(DeploymentRequestPolicy.ENDPOINT);
        if(!"https".equals(url.getProtocol())||!"api.preceptoros.org".equals(url.getHost())
            ||url.getPort()!=-1)throw new IllegalStateException("destination_not_authorized");
        HttpsURLConnection conn=(HttpsURLConnection)url.openConnection();
        conn.setInstanceFollowRedirects(false);
        conn.setConnectTimeout(6000);conn.setReadTimeout(7000);
        conn.setRequestMethod("POST");conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type","application/json");
        conn.setRequestProperty("Accept","application/json");
        conn.setRequestProperty("Cache-Control","no-store");
        try{
            try(OutputStream out=conn.getOutputStream()){
                out.write(body.getBytes(StandardCharsets.UTF_8));out.flush();
            }
            int code=conn.getResponseCode();
            if(code!=200&&code!=202)throw new IllegalStateException("intake_http_"+code);
            String contentType=conn.getContentType();
            if(contentType==null||!contentType.toLowerCase().startsWith("application/json"))
                throw new IllegalStateException("intake_wrong_content_type");
            if(conn.getContentLengthLong()>MAX_REPLY_BYTES)throw new IllegalStateException("reply_too_large");
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(InputStream input=conn.getInputStream()){
                byte[] block=new byte[512];int n;
                while((n=input.read(block))!=-1){
                    if(bytes.size()+n>MAX_REPLY_BYTES)throw new IllegalStateException("reply_too_large");
                    bytes.write(block,0,n);
                }
            }
            JSONObject receipt=new JSONObject(bytes.toString(StandardCharsets.UTF_8.name()));
            if(!DeploymentRequestPolicy.validReceipt(code,
                receipt.optString("schema",""),receipt.optString("request_id",""),
                receipt.optString("state",""),receipt.optString("received_at",""),
                receipt.optString("authority",""),receipt.optString("credential",""),
                receipt.optString("live",""),expectedHash)||
                !DeploymentRequestPolicy.validNotification(receipt.optString("notification","")))
                throw new IllegalStateException("unverified_intake_receipt");
            if(!"NO_DATA(recipient_notification_not_verified)".equals(receipt.optString("owner_alert","")))
                throw new IllegalStateException("unverified_notification_claim");
            JSONObject result=new JSONObject();
            result.put("contractVerified",true);
            result.put("preliminaryReceiptValidated",true);
            result.put("trackingId",expectedHash);result.put("node",node);
            result.put("state","PENDING");
            result.put("approved",false);result.put("live",false);
            return result;
        }finally{conn.disconnect();}
    }
    private static String normalize(Exception error){
        String msg=error.getMessage();
        if(msg!=null&&msg.matches("(intake_http_[0-9]{3}|unverified_intake_receipt|intake_wrong_content_type|reply_too_large|unverified_notification_claim|local_identity_storage_unavailable|local_pending_storage_unavailable|destination_not_authorized)"))
            return msg;
        return "network_or_runtime_unavailable";
    }
}
