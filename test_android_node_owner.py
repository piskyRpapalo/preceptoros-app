"""«Create my node» on Android: the native crypto must match RFC 8032, OpenSSH and Aduana's canonical JSON."""
import json, shutil, subprocess, tempfile, unittest
from pathlib import Path

SRC = Path(__file__).parent / "mvp-android/app/src/main/java/org/preceptoros/mvp"
PROBE = """package org.preceptoros.mvp;
import java.nio.file.*; import java.util.*;
public class NodeProbe { public static void main(String[] a) throws Exception {
  byte[] seed = NodeCrypto.unhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60");
  System.out.println(NodeCrypto.hex(NodeCrypto.publicKey(seed)));
  System.out.println(NodeCrypto.hex(NodeCrypto.sign(seed, new byte[0])));
  Map<String,Object> m = new HashMap<>(); m.put("z", "a\\nb\\"\\\\\\u00e9\\u0001"); m.put("a", List.of(1L, true, Map.of("k", "v"))); m.put("n", null);
  System.out.println(NodeCrypto.canonical(m));
  System.out.println(NodeCrypto.canonical(NodeCrypto.parse(NodeCrypto.canonical(m))));
  byte[] msg = NodeCrypto.canonicalBytes(Map.of("esquema", "preceptoros.plan-nodo/1"));
  Files.write(Paths.get(a[0], "msg"), msg);
  Files.writeString(Paths.get(a[0], "msg.sig"), NodeCrypto.sshsig(seed, "preceptoros-plan-nodo", msg));
  Files.writeString(Paths.get(a[0], "allowed"), "owner " + NodeCrypto.publicLine(seed) + "\\n");
}}
"""

@unittest.skipUnless(shutil.which("javac") and shutil.which("ssh-keygen"), "javac and ssh-keygen required")
class NodeCryptoContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        pkg = cls.tmp / "src/org/preceptoros/mvp"; pkg.mkdir(parents=True)
        shutil.copy(SRC / "NodeCrypto.java", pkg); (pkg / "NodeProbe.java").write_text(PROBE)
        subprocess.run(["javac", "-nowarn", "-d", str(cls.tmp / "out"), *map(str, pkg.glob("*.java"))], check=True, capture_output=True)
        cls.lines = subprocess.run(["java", "-cp", str(cls.tmp / "out"), "org.preceptoros.mvp.NodeProbe", str(cls.tmp)],
                                   check=True, capture_output=True, text=True).stdout.splitlines()

    def test_rfc8032_vector_1(self):
        self.assertEqual(self.lines[0], "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        self.assertEqual(self.lines[1], "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")

    def test_canonical_json_matches_python_and_round_trips(self):
        want = json.dumps({"z": "a\nb\"\\é\u0001", "a": [1, True, {"k": "v"}], "n": None},
                          sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        self.assertEqual(self.lines[2], want)
        self.assertEqual(self.lines[3], want)

    def test_sshsig_verifies_with_openssh_only_in_its_namespace(self):
        def verify(ns):
            with open(self.tmp / "msg", "rb") as msg:
                return subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(self.tmp / "allowed"), "-I", "owner",
                                       "-n", ns, "-s", str(self.tmp / "msg.sig")], stdin=msg, capture_output=True).returncode
        self.assertEqual(verify("preceptoros-plan-nodo"), 0)
        self.assertNotEqual(verify("preceptoros-cedula"), 0)

class NodeOwnerBoundaries(unittest.TestCase):
    def test_private_material_never_reaches_javascript_and_destinations_are_fixed(self):
        bridge = (SRC / "NodeOwnerBridge.java").read_text()
        owner = (SRC / "NodeOwner.java").read_text()
        js = (Path(__file__).parent / "mvp-android/android_node_bridge.js").read_text()
        self.assertIn('"https://api.preceptoros.org"', bridge)
        self.assertIn("setInstanceFollowRedirects(false)", bridge)
        self.assertIn("OwnerFrameAccess.accepts(", bridge)
        self.assertEqual(bridge.count("confirm("), 3)   # create + build, plus the definition
        for secret in ("hb_key", "owner.seed", "firma_ssh"):
            self.assertNotIn(secret, js)
        self.assertNotIn('"hb_key"', owner.split("private Map<String, Object> result(")[1].split("}")[0])
        self.assertNotIn('"APPROVED"', owner)   # the device never decides; the Sovereign does

BEAT_PROBE = """package org.preceptoros.mvp;
import java.io.File; import java.nio.file.*; import java.time.Instant; import java.util.*;
public class BeatProbe { public static void main(String[] a) throws Exception {
  File dir = new File(a[0]); List<String> sent = new ArrayList<>();
  NodeOwner.Http http = (path, body, key) -> {
    Map<?,?> m = (Map<?,?>) NodeCrypto.parse(new String(body, "UTF-8"));
    sent.add(path + " " + (m.get("secuencia") == null ? "-" : m.get("secuencia")) + " " + (key == null ? "nokey" : key.substring(0, 6)) + " " + m.get("medido_en"));
    Map<String,Object> r = new HashMap<>();
    if (path.equals("/api/v1/latidos/llaves")) { r.put("estado", "registrada"); r.put("nodo", m.get("nodo")); }
    return new NodeOwner.Reply(202, r); };
  NodeOwner o = new NodeOwner(dir, http);
  System.out.println("alias_before=" + o.beatingAlias());
  Map<String,Object> s = new LinkedHashMap<>(); s.put("request_id", "r"); s.put("cedula_receipt", "c"); s.put("node", "nodo.3.tank-3");
  s.put("alias", "tank-3"); s.put("hb_key", "aaaaaaaa"); s.put("hb_hasta", a[1]); s.put("seq", 1763900000L);
  Files.write(new File(dir, "state.json").toPath(), NodeCrypto.canonicalBytes(s));
  System.out.println("alias_after=" + o.beatingAlias());
  Instant now = Instant.parse("2026-11-24T18:00:00Z");
  System.out.println("state=" + o.advance(now).get("state"));
  System.out.println("state=" + o.advance(now).get("state"));
  for (String x : sent) System.out.println("sent " + x);
}}
"""

@unittest.skipUnless(shutil.which("javac"), "javac required")
class NodeOwnerServiceBeat(unittest.TestCase):
    """The presence service beats through NodeOwner.advance: the phone-born key, renewed before it expires, and a
    sequence that continues the chain Aduana already holds (max(last+1, epoch seconds)) — never a counter from 0."""
    def run_probe(self, hasta):
        tmp = Path(tempfile.mkdtemp()); pkg = tmp / "src/org/preceptoros/mvp"; pkg.mkdir(parents=True)
        for f in ("NodeCrypto.java", "NodeOwner.java", "DeploymentRequestPolicy.java"): shutil.copy(SRC / f, pkg)
        (pkg / "BeatProbe.java").write_text(BEAT_PROBE)
        subprocess.run(["javac", "-nowarn", "-d", str(tmp / "out"), *map(str, pkg.glob("*.java"))], check=True, capture_output=True)
        (tmp / "state").mkdir()
        return subprocess.run(["java", "-cp", str(tmp / "out"), "org.preceptoros.mvp.BeatProbe", str(tmp / "state"), hasta],
                              check=True, capture_output=True, text=True).stdout.splitlines()

    def test_fresh_key_beats_with_increasing_epoch_sequence(self):
        out = self.run_probe("2026-11-25T17:00:00Z")
        self.assertIn("alias_before=null", out); self.assertIn("alias_after=tank-3", out)
        sent = [l for l in out if l.startswith("sent ")]
        self.assertEqual([l.split()[1] for l in sent], ["/api/v1/latidos"] * 2)
        seqs = [int(l.split()[2]) for l in sent]
        self.assertEqual(seqs[0], 1795543200)               # 2026-11-24T18:00:00Z in epoch seconds, above the old 1763900000
        self.assertEqual(seqs[1], seqs[0] + 1)              # same second: still strictly increasing
        self.assertTrue(all(l.split()[3] == "aaaaaa" for l in sent))
        self.assertEqual(out.count("state=MEASURED"), 2)
        self.assertTrue(all(l.split()[4] == "2026-11-24T17:59:58Z" for l in sent))   # 2 s before now: never medicion_futura

    def test_key_near_expiry_is_renewed_before_the_beat(self):
        out = self.run_probe("2026-11-24T23:00:00Z")    # 5 h left (< 12 h): renew first
        sent = [l.split()[1:] for l in out if l.startswith("sent ")]
        self.assertEqual(sent[0][0], "/api/v1/latidos/llaves"); self.assertEqual(sent[0][2], "nokey")
        self.assertEqual(sent[1][0], "/api/v1/latidos"); self.assertNotEqual(sent[1][2], "aaaaaa")   # beats with the new key

class PresenceServiceOneEmitter(unittest.TestCase):
    def test_service_uses_the_device_node_and_the_app_tick_steps_aside(self):
        service = (SRC / "HeartbeatPresenceService.java").read_text()
        bridge = (SRC / "NodeOwnerBridge.java").read_text()
        sbridge = (SRC / "HeartbeatServiceBridge.java").read_text()
        self.assertIn("NodeOwnerBridge.owner(this).advance(", service)
        self.assertIn("synchronized (NodeOwner.LOCK)", service)
        tick = bridge.split("private void tick()")[1].split("\n    }\n")[0]
        self.assertNotIn("ready_to_build", tick)             # no periodic APP beat: revoke stays revoked when the APP opens
        self.assertNotIn("lastBeat", bridge)
        self.assertIn("synchronized (NodeOwner.LOCK)", bridge)
        self.assertIn("beatingAlias()", sbridge)            # a phone-born node needs no imported file
        self.assertIn("openPicker()", sbridge)              # any other node keeps the picker
        self.assertIn("minusSeconds(NodeOwner.CLOCK_MARGIN_SECONDS)", (SRC / "HeartbeatSender.java").read_text())

    def test_an_update_or_an_open_app_brings_a_consented_service_back_without_a_second_chain(self):
        receiver = (SRC / "HeartbeatBootReceiver.java").read_text()
        manifest = (SRC.parents[3] / "AndroidManifest.xml").read_text()
        service = (SRC / "HeartbeatPresenceService.java").read_text()
        bridge = (SRC / "NodeOwnerBridge.java").read_text()
        self.assertIn("android.intent.action.MY_PACKAGE_REPLACED", manifest)
        self.assertIn("ACTION_MY_PACKAGE_REPLACED.equals(action) && HeartbeatCredentialStore.consentActive(context)", receiver)
        self.assertIn("ACTION_BOOT_COMPLETED.equals(action) && HeartbeatCredentialStore.autoResume(context)", receiver)  # boot stays opt-in
        self.assertEqual(service.count("if (!looping) { looping = true; handler.post(tick); }"), 2)
        self.assertIn("if (serviceBeats) {", bridge)

    def test_a_sticky_restart_without_on_start_command_still_beats(self):
        # Tank 3 2026-11-24 19:51Z: the APP swiped from recents killed the process; Android recreated the service
        # (onCreate) but never delivered onStartCommand, so nothing beat. onCreate starts the chain under consent.
        service = (SRC / "HeartbeatPresenceService.java").read_text()
        create = service.split("public void onCreate()")[1].split("\n    }\n")[0]
        self.assertIn("HeartbeatCredentialStore.consentActive(this)", create)
        self.assertIn("if (consent && !looping) { looping = true; handler.post(tick); }", create)
        self.assertNotRegex(service, r"Log\.i\([^;]*(key|Key|secret)")   # logs carry alias, action and cause only


PUBLIC_PROBE = """package org.preceptoros.mvp;
import java.time.Instant;
public class PublicProbe { public static void main(String[] a) throws Exception {
  Instant t = Instant.parse("2026-11-24T21:00:00.400Z");
  String w = "{\\"colonia\\":{\\"nodes\\":[{\\"id\\":\\"tank-3\\",\\"seal\\":\\"LIVE\\",\\"since\\":\\"2026-11-24\\"},{\\"id\\":\\"odd\\",\\"seal\\":\\"MAYBE\\"}]}}";
  System.out.println(PublicNodeState.classify(NodeCrypto.parse(w), "tank-3", t));
  System.out.println(PublicNodeState.classify(NodeCrypto.parse(w), "doggee-s110", t));
  System.out.println(PublicNodeState.classify(NodeCrypto.parse(w), "odd", t));
  System.out.println(PublicNodeState.classify(NodeCrypto.parse("{}"), "tank-3", t));
  System.out.println(PublicNodeState.classify(null, null, t));
} }
"""

@unittest.skipUnless(shutil.which("javac"), "javac required")
class PublicNodeStateForAcho(unittest.TestCase):
    """Sovereign 2026-11-24: the APP shows what the public OpenWorld says about this phone's node, with state, cause,
    source and age. Absence is NO_DATA with its cause, never OFFLINE; an unknown seal is NO_DATA too."""
    def test_classify(self):
        tmp = Path(tempfile.mkdtemp()); pkg = tmp / "src/org/preceptoros/mvp"; pkg.mkdir(parents=True)
        for f in ("NodeCrypto.java", "PublicNodeState.java"): shutil.copy(SRC / f, pkg)
        (pkg / "PublicProbe.java").write_text(PUBLIC_PROBE)
        subprocess.run(["javac", "-nowarn", "-d", str(tmp / "out"), *map(str, pkg.glob("*.java"))], check=True, capture_output=True)
        live, absent, odd, empty, none = subprocess.run(["java", "-cp", str(tmp / "out"), "org.preceptoros.mvp.PublicProbe"],
            check=True, capture_output=True, text=True).stdout.splitlines()
        src = "source=https://preceptoros.org/api/world-state, checked_at=2026-11-24T21:00:00Z"
        self.assertEqual(live, "{kind=public_state, state=LIVE, cause=, " + src + ", node=tank-3, since=2026-11-24}")
        self.assertIn("state=NO_DATA, cause=node_not_in_public_feed", absent)   # absence is never OFFLINE
        self.assertIn("state=NO_DATA, cause=seal_not_recognised", odd)
        self.assertIn("state=NO_DATA, cause=world_state_without_nodes", empty)
        self.assertIn("state=NO_DATA, cause=no_beating_node_on_this_phone", none)

    def test_wired_to_the_bridge_and_both_panels(self):
        bridge = (SRC / "NodeOwnerBridge.java").read_text()
        js = (SRC.parents[6] / "android_node_bridge.js").read_text()
        gen = (SRC.parents[7] / "bin/package_public_mini.py").read_text()
        self.assertIn('case "public_state": background(rid, reply, () -> PublicNodeState.read(owner.beatingAlias()));', bridge)
        self.assertIn('doc.getElementById("openworld-node-state")', js)
        self.assertIn('id="openworld-node-state"', gen)
        self.assertNotIn("Your Companion is not LIVE", gen)   # the old fixed sentence lied while the node was LIVE

if __name__ == "__main__":
    unittest.main()
