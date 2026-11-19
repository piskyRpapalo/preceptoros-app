package org.preceptoros.mvp;
public final class DeploymentRequestPolicyTest {
 static int count=0;
 private static void yes(boolean x,String reason){count++;if(!x)throw new AssertionError(reason);}
 private static final String H="a".repeat(64),N="b".repeat(32);
 public static void main(String[] args){
  if(args.length==1&&"--fixture".equals(args[0])){
    String fixture=DeploymentRequestPolicy.buildBody("nodo.42.alice",H,N);
    System.out.println(fixture);
    System.out.println(DeploymentRequestPolicy.sha256(fixture));
    return;
  }

  yes(DeploymentRequestPolicy.validNode("nodo.42.alice"),"valid node");
  yes(!DeploymentRequestPolicy.validNode("nodo.alice"),"reject malformed node");
  yes(!DeploymentRequestPolicy.validNode("nodo.42.<script>"),"reject injected node");
  yes(DeploymentRequestPolicy.validPurpose("Research node"),"valid purpose");
  yes(!DeploymentRequestPolicy.validPurpose("\n"),"reject no purpose");
  yes(!DeploymentRequestPolicy.validPurpose("a".repeat(513)),"limit purpose");
  String body=DeploymentRequestPolicy.buildBody("nodo.42.alice",H,N);
  yes(body.equals("{\"consent\":true,\"device_sha256\":\""+H+"\",\"node\":\"nodo.42.alice\",\"nonce\":\""+N+"\",\"schema\":\"preceptoros.deployment-request/1\"}"),"canonical body");
  String digest=DeploymentRequestPolicy.sha256(body);
  yes(digest.matches("[a-f0-9]{64}"),"digest");
  yes(digest.equals(DeploymentRequestPolicy.sha256(body)),"idempotent hash");
  yes(!digest.equals(DeploymentRequestPolicy.sha256(DeploymentRequestPolicy.buildBody("nodo.42.alice",H,"c".repeat(32)))),"fresh nonce");
  yes(DeploymentRequestPolicy.validReceipt(202,DeploymentRequestPolicy.RECEIPT_SCHEMA,digest,"AWAITING_HUMAN","2026-11-19T05:00:00.000Z","NONE","NOT_PROVISIONED","NO_DATA(heartbeat_not_verified)",digest),"new pending receipt");
  yes(DeploymentRequestPolicy.validReceipt(200,DeploymentRequestPolicy.RECEIPT_SCHEMA,digest,"AWAITING_HUMAN","2026-11-19T05:00:00.000Z","NONE","NOT_PROVISIONED","NO_DATA(heartbeat_not_verified)",digest),"replay pending receipt");
  yes(!DeploymentRequestPolicy.validReceipt(202,DeploymentRequestPolicy.RECEIPT_SCHEMA,"c".repeat(64),"AWAITING_HUMAN","2026-11-19T05:00:00.000Z","NONE","NOT_PROVISIONED","NO_DATA(heartbeat_not_verified)",digest),"reject substitution");
  yes(!DeploymentRequestPolicy.validReceipt(202,DeploymentRequestPolicy.RECEIPT_SCHEMA,digest,"APPROVED","2026-11-19T05:00:00.000Z","NONE","NOT_PROVISIONED","NO_DATA(heartbeat_not_verified)",digest),"no automatic approval");
  yes(!DeploymentRequestPolicy.validReceipt(202,DeploymentRequestPolicy.RECEIPT_SCHEMA,digest,"LIVE","2026-11-19T05:00:00.000Z","NONE","NOT_PROVISIONED","NO_DATA(heartbeat_not_verified)",digest),"no automatic LIVE");
  yes(!DeploymentRequestPolicy.validReceipt(302,DeploymentRequestPolicy.RECEIPT_SCHEMA,digest,"AWAITING_HUMAN","2026-11-19T05:00:00.000Z","NONE","NOT_PROVISIONED","NO_DATA(heartbeat_not_verified)",digest),"redirect is not receipt");
  yes(DeploymentRequestPolicy.validNotification("QUEUED"),"queued notification");
  yes(!DeploymentRequestPolicy.validNotification("HUMAN_CONFIRMED"),"fake delivery");
  System.out.println("PASS "+count+" deployment client policy gates");
 }
}
