package org.preceptoros.mvp;
final class HeartbeatOncePolicyTest {
  static int cases=0;
  static void check(boolean actual,String label){
    cases++;
    if(!actual)throw new AssertionError(label);
  }
  static void bad(Runnable f,String label){
    boolean refused=false;
    try{f.run();}catch(IllegalArgumentException expected){refused=true;}
    check(refused,label);
  }
  public static void main(String[] args) {
    String node="nodo.42.owner",measured="2026-11-20T13:00:00Z";
    String received="2026-11-20T13:00:01.000Z";
    check(HeartbeatOncePolicy.node(node),"canonical node");
    check(!HeartbeatOncePolicy.node("primer-ancla"),"no legacy alias");
    check(!HeartbeatOncePolicy.node("nodo.42.owner\nsecret"),"no newline injection");
    check(!HeartbeatOncePolicy.node("nodo.42.owner\""),"no JSON injection");
    check(HeartbeatOncePolicy.key("a".repeat(64)),"lower-case secret");
    check(!HeartbeatOncePolicy.key("A".repeat(64)),"uppercase key refused");
    check(!HeartbeatOncePolicy.key("f".repeat(63)),"short key refused");
    check(!HeartbeatOncePolicy.key("b".repeat(64)+"\n"),"trailing line refused");
    check(HeartbeatOncePolicy.sequence(0),"sequence zero");
    check(HeartbeatOncePolicy.sequence(9007199254740991L),"last safe seq");
    check(!HeartbeatOncePolicy.sequence(-1),"negative seq refused");
    check(!HeartbeatOncePolicy.sequence(9007199254740992L),"unsafe seq refused");
    check(HeartbeatOncePolicy.utc(measured),"utc accepted");
    check(HeartbeatOncePolicy.utc(received),"millis accepted");
    check(!HeartbeatOncePolicy.utc("2026-13-20T13:00:00Z"),"calendar invalid");
    check(!HeartbeatOncePolicy.utc("2026-11-20T13:00:00+00:00"),"UTC Z required");
    check(!HeartbeatOncePolicy.utc("2026-11-20T13:00:00.0000Z"),"precision max 3");
    String expected="{\"esquema\":\"preceptoros.latido/1\",\"medido_en\":\"2026-11-20T13:00:00Z\",\"nodo\":\"nodo.42.owner\",\"secuencia\":7}";
    check(expected.equals(HeartbeatOncePolicy.body(node,7,measured)),"exact worker field order");
    check("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad".equals(
      HeartbeatOncePolicy.digest("abc")),"sha256 golden vector");
    String payload="fdf2e300a5dc2584eb1b0953e4b8644dee9a97526283adb9a85c3f5c6dcbad97";
    String receipt="5dcbb7c3411fd347fbb7bf0f0f5ce480559baa629d4593a0f19b028efa5f2044";
    check(payload.equals(HeartbeatOncePolicy.digest(expected)),"cross-language payload golden");
    check(HeartbeatOncePolicy.receipt(202,node,7,measured,received,payload,receipt),"worker receipt golden");
    check(HeartbeatOncePolicy.receipt(200,node,7,measured,received,payload,receipt),"replay 200 receipt");
    check(!HeartbeatOncePolicy.receipt(401,node,7,measured,received,payload,receipt),"reject auth failure");
    check(!HeartbeatOncePolicy.receipt(201,node,7,measured,received,payload,receipt),"reject unusual status");
    check(!HeartbeatOncePolicy.receipt(202,"nodo.42.other",7,measured,received,payload,receipt),"reject cross node");
    check(!HeartbeatOncePolicy.receipt(202,node,8,measured,received,payload,receipt),"reject seq replay");
    check(!HeartbeatOncePolicy.receipt(202,node,7,measured,received,payload,"0".repeat(64)),"reject fake receipt hash");
    check(!HeartbeatOncePolicy.receipt(202,node,7,measured,received,"0".repeat(64),receipt),"reject fake payload hash");
    check(!HeartbeatOncePolicy.receipt(202,node,7,measured,"2026-11-20T13:00:02.000Z",payload,receipt),"reject altered server time");
    bad(()->HeartbeatOncePolicy.body("nodo.42.other\"",7,measured),"reject escaped node");
    bad(()->HeartbeatOncePolicy.body(node,-1,measured),"reject negative number");
    bad(()->HeartbeatOncePolicy.body(node,7,"tomorrow"),"reject invalid UTC");
    System.out.println("PASS "+cases+"/"+cases+" pure Java native heartbeat contract");
  }
}
