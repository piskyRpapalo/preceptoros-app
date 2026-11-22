"""Synthetic boundary tests; actual native voice measurement is separate."""
import hashlib
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import wave

import voz_lectura as V


class NativeReading(unittest.TestCase):
    def test_invalid_requests_never_start_an_engine(self):
        with patch.object(V.subprocess, 'run') as run:
            for request in ({}, {'text':'test','engine':'other'},
                            {'text':'test','engine':'host-espeak-ng','extra':1},
                            {'text':'test','engine':'host-espeak-ng','language':'fr'},
                            {'text':'test','engine':'host-espeak-ng','language':'es-ES'},
                            {'text':'test','engine':'host-espeak-ng','language':'es;rm'},
                            {'text':'test','engine':'host-espeak-ng','language':None},
                            {'text':'x'*961,'engine':'host-espeak-ng'},
                            {'text':'\x00','engine':'host-espeak-ng'}):
                with self.assertRaises(V.ReadingUnavailable): V.synthesize(request)
            run.assert_not_called()

    def test_hardware_switch_and_missing_engine_deny(self):
        with patch.object(V.silencio, 'apagado', return_value=True):
            with self.assertRaisesRegex(V.ReadingUnavailable,'hardware_declared_off'):
                V.synthesize({'text':'test','engine':'host-espeak-ng'})
        with patch.object(V.silencio,'apagado',return_value=False), patch.object(V.shutil,'which',return_value=None):
            with self.assertRaisesRegex(V.ReadingUnavailable,'unavailable'):
                V.synthesize({'text':'test','engine':'host-espeak-ng'})

    def test_fixture_wave_receipt_is_bound_to_text_and_audio(self):
        text='Synthetic test, not a model answer.'
        def synth(args, **kwargs):
            self.assertEqual(kwargs['input'],text.encode())
            self.assertNotIn('shell',kwargs)
            with wave.open(args[-1],'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050);w.writeframes(b'\0'*4410)
            return subprocess.CompletedProcess(args,0)
        with patch.object(V.silencio,'apagado',return_value=False),patch.object(V.shutil,'which',return_value='fixture-espeak'),patch.object(V.subprocess,'run',side_effect=synth):
            audio,receipt=V.synthesize({'text':text,'engine':'host-espeak-ng'})
        self.assertEqual(receipt['text_sha256'],hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(receipt['audio_sha256'],hashlib.sha256(audio).hexdigest())


    def test_spanish_voice_is_strictly_local_and_receipted(self):
        seen = []
        def fixture(args, **kwargs):
            seen.append(args)
            self.assertEqual(args[args.index('-v')+1], 'es')
            self.assertNotIn('shell', kwargs)
            with wave.open(args[-1], 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
                w.writeframes(b'\0' * 4410)
            return subprocess.CompletedProcess(args, 0)
        with patch.object(V.silencio, 'apagado', return_value=False), \
             patch.object(V.shutil, 'which', return_value='fixture-espeak'), \
             patch.object(V.subprocess, 'run', side_effect=fixture):
            wav, receipt = V.synthesize({
                'text': 'Hola, estado local.', 'engine': 'host-espeak-ng', 'language': 'es'
            })
        self.assertEqual(len(seen), 1)
        self.assertEqual(receipt['state'], 'ok')
        self.assertEqual(receipt['engine'], 'host-espeak-ng')
        self.assertEqual(receipt['language'], 'es')
        self.assertEqual(receipt['audio_sha256'], hashlib.sha256(wav).hexdigest())
        self.assertGreaterEqual(receipt['synthesis_wall_ms'], 0)

    def test_timeout_denies_and_releases_the_synthesis_lock(self):
        with patch.object(V.silencio,'apagado',return_value=False),patch.object(V.shutil,'which',return_value='fixture-espeak'),patch.object(V.subprocess,'run',side_effect=subprocess.TimeoutExpired('fixture',15)):
            with self.assertRaises(V.ReadingUnavailable):V.synthesize({'text':'test','engine':'host-espeak-ng'})
        self.assertTrue(V._LOCK.acquire(blocking=False));V._LOCK.release()

    def test_browser_local_only_chunk_and_stop_cases(self):
        root=Path(__file__).resolve().parent
        result=subprocess.run(['node','--test','tests/native_voice_cases.cjs'],cwd=root,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

# B-04: reuse registered voice suite for no-hardware STT security checks.
import json
import tempfile
import oido
import voz_stt_local as S

def fixture_wav(frames=32000, channels=1, rate=16000, sampwidth=2):
    buf=io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(b"\0" * frames * channels * sampwidth)
    return buf.getvalue()


class LocalSTT(unittest.TestCase):
    def setUp(self):
        self.request={"command": S.COMMAND}
        self.wav=fixture_wav()

    def test_import_is_inert(self):
        self.assertEqual(S.COMMAND, "transcribe_es_pcm16_v1")

    def test_origin_denial_precedes_audio_and_model(self):
        with patch.object(S.oido,"transcribir") as infer:
            with self.assertRaisesRegex(S.STTUnavailable, "local_origin_required"):
                S.transcribe_once(self.request,self.wav)
            infer.assert_not_called()

    def test_wrong_command_and_extra_keys_fail(self):
        with patch.object(S.oido,"transcribir") as infer:
            for request in ({},{"command":"record_es_once"},{"command":S.COMMAND,"admin":True},None):
                with self.assertRaisesRegex(S.STTUnavailable,"explicit_es_transcription_required"):
                    S.transcribe_once(request,self.wav,local_origin_verified=True)
            infer.assert_not_called()

    def test_kill_switch_denies_before_inference(self):
        with patch.object(S.silencio,"apagado",return_value=True),patch.object(S.oido,"transcribir") as infer:
            with self.assertRaisesRegex(S.STTUnavailable, "hardware_declared_off"):
                S.transcribe_once(self.request,self.wav,local_origin_verified=True)
            infer.assert_not_called()

    def test_bad_wav_rejected_before_model(self):
        with patch.object(S.silencio,"apagado",return_value=False),patch.object(S.oido,"transcribir") as infer:
            for data in (b"",b"abc",b"RIFFbad!",b"A"*200000,fixture_wav(rate=48000),fixture_wav(channels=2),fixture_wav(frames=4000),fixture_wav(frames=100000),fixture_wav(sampwidth=1)):
                with self.assertRaises(S.STTUnavailable):
                    S.transcribe_once(self.request,data,local_origin_verified=True)
            infer.assert_not_called()

    def test_cpu_overheat_denies_before_model(self):
        with patch.object(S.silencio,"apagado",return_value=False),patch.object(S,"_temperature_c",return_value=88.8),patch.object(S.oido,"transcribir") as infer:
            with self.assertRaisesRegex(S.STTUnavailable,"beelink_cpu_thermal_hold"):
                S.transcribe_once(self.request,self.wav,local_origin_verified=True)
            infer.assert_not_called()

    def test_missing_sensor_denies(self):
        with patch.object(S.silencio,"apagado",return_value=False),patch.object(S,"_temperature_c",side_effect=S.STTUnavailable("cpu_thermal_sensor_unavailable")),patch.object(S.oido,"transcribir") as infer:
            with self.assertRaisesRegex(S.STTUnavailable,"cpu_thermal_sensor_unavailable"):
                S.transcribe_once(self.request,self.wav,local_origin_verified=True)
            infer.assert_not_called()

    def test_missing_engine_denies(self):
        with patch.object(S.silencio,"apagado",return_value=False),patch.object(S,"_temperature_c",return_value=50),patch.object(S.oido,"oido_disponible",return_value=False),patch.object(S.oido,"transcribir") as infer:
            with self.assertRaisesRegex(S.STTUnavailable,"local_whisper_cpp_or_model_missing"):
                S.transcribe_once(self.request,self.wav,local_origin_verified=True)
            infer.assert_not_called()

    def test_concurrent_call_is_refused(self):
        with patch.object(S.silencio,"apagado",return_value=False),patch.object(S,"_temperature_c",return_value=50),patch.object(S.oido,"oido_disponible",return_value=True),patch.object(S.oido,"transcribir") as infer:
            self.assertTrue(S._LOCK.acquire(False))
            try:
                with self.assertRaisesRegex(S.STTUnavailable,"local_stt_busy"):
                    S.transcribe_once(self.request,self.wav,local_origin_verified=True)
            finally:
                S._LOCK.release()
            infer.assert_not_called()

    def test_success_is_a_transcript_not_a_permission_or_brain_reply(self):
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/"fixture-model";model.write_bytes(b"not-real-model")
            captured=[]
            def fake(path, idioma, **limits):
                captured.append((Path(path).read_bytes(),idioma,path,limits))
                return "Hola, voz local."
            with patch.object(S.silencio,"apagado",return_value=False),patch.object(S,"_temperature_c",return_value=52),patch.object(S.oido,"oido_disponible",return_value=True),patch.object(S.oido,"WHISPER_MODEL",str(model)),patch.object(S.oido,"transcribir",side_effect=fake):
                result=S.transcribe_once(self.request,self.wav,local_origin_verified=True)
            self.assertEqual(captured[0][0],self.wav)
            self.assertEqual(captured[0][1],"es")
            self.assertEqual(captured[0][3],{"cpu_only":True,"threads":2,"timeout_sec":25})
            self.assertFalse(Path(captured[0][2]).exists(),"audio must be deleted")
            self.assertEqual(result["model_sha256"],hashlib.sha256(model.read_bytes()).hexdigest())
            self.assertEqual(result["audio_sha256"],hashlib.sha256(self.wav).hexdigest())
            self.assertEqual(result["text"],"Hola, voz local.")
            self.assertEqual(result["cause"],"not_authenticated_brain_reply")
            self.assertNotIn("authority",result)
            self.assertLess(len(json.dumps(result,ensure_ascii=False,separators=(",",":")).encode()),1024)

    def test_overheat_after_inference_discards_answer(self):
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/"model";model.write_bytes(b"model")
            with patch.object(S.silencio,"apagado",return_value=False),patch.object(S,"_temperature_c",side_effect=[52,89]),patch.object(S.oido,"oido_disponible",return_value=True),patch.object(S.oido,"WHISPER_MODEL",str(model)),patch.object(S.oido,"transcribir",return_value="hola"):
                with self.assertRaisesRegex(S.STTUnavailable,"beelink_cpu_thermal_hold_after_transcription"):
                    S.transcribe_once(self.request,self.wav,local_origin_verified=True)

    def test_empty_transcript_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/"model";model.write_bytes(b"model")
            with patch.object(S.silencio,"apagado",return_value=False),patch.object(S,"_temperature_c",return_value=52),patch.object(S.oido,"oido_disponible",return_value=True),patch.object(S.oido,"WHISPER_MODEL",str(model)),patch.object(S.oido,"transcribir",return_value=""):
                with self.assertRaisesRegex(S.STTUnavailable,"local_stt_no_transcript"):
                    S.transcribe_once(self.request,self.wav,local_origin_verified=True)

    def test_invalid_result_never_leaks_private_text(self):
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/"model";model.write_bytes(b"model")
            with patch.object(S.silencio,"apagado",return_value=False),patch.object(S,"_temperature_c",return_value=52),patch.object(S.oido,"oido_disponible",return_value=True),patch.object(S.oido,"WHISPER_MODEL",str(model)),patch.object(S.oido,"transcribir",side_effect=RuntimeError("private microphone raw text")):
                with self.assertRaisesRegex(S.STTUnavailable,"^local_stt_executor_failed$"):
                    S.transcribe_once(self.request,self.wav,local_origin_verified=True)


class STTConstraints(unittest.TestCase):
    def test_no_gpu_two_threads_timeout(self):
        captured=[]
        def fixture(argv,**kwargs):
            captured.append((argv,kwargs))
            return subprocess.CompletedProcess(argv,0,stdout="Hola local.\n")
        with patch.object(oido,"oido_disponible",return_value=True),patch.object(oido.subprocess,"run",side_effect=fixture):
            actual=oido.transcribir("fixture.wav",idioma="es",cpu_only=True,threads=2,timeout_sec=25)
        self.assertEqual(actual,"Hola local.")
        argv,kwargs=captured[0]
        self.assertIn("--no-gpu",argv)
        self.assertEqual(argv[argv.index("--threads")+1],"2")
        self.assertEqual(kwargs["timeout"],25)
        self.assertNotIn("shell",kwargs)

    def test_bad_cpu_budget_rejected_before_subprocess(self):
        with patch.object(oido,"oido_disponible",return_value=True),patch.object(oido.subprocess,"run") as fake:
            for threads in (0,5,True,"2"):
                self.assertIsNone(oido.transcribir("fixture.wav",cpu_only=True,threads=threads))
            for timeout in (0,61,True,"25"):
                self.assertIsNone(oido.transcribir("fixture.wav",cpu_only=True,timeout_sec=timeout))
            fake.assert_not_called()

    def test_legacy_caller_unchanged(self):
        with patch.object(oido,"oido_disponible",return_value=True),patch.object(oido.subprocess,"run",return_value=subprocess.CompletedProcess([],0,stdout="legacy\n")) as fake:
            self.assertEqual(oido.transcribir("fixture.wav"),"legacy")
        args=fake.call_args.args[0]
        self.assertNotIn("--no-gpu",args)
        self.assertNotIn("--threads",args)
        self.assertEqual(fake.call_args.kwargs["timeout"],60)

# B-05 route tests inspect the actual handler method without opening sockets,
# recording any microphone, importing inference into a fake web server, or
# contacting a remote speech provider.
import ast
from email.message import Message
from types import SimpleNamespace

class B05HTTPSTT(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parent / "bin" / "preceptoros-pwa"
        tree = ast.parse(source.read_text())
        clsdef = next(x for x in tree.body if isinstance(x, ast.ClassDef) and any(
            isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name == "_stt_local_wav"
            for f in x.body))
        f = next(f for f in clsdef.body if isinstance(f, ast.FunctionDef) and f.name == "_stt_local_wav")
        code = compile(ast.fix_missing_locations(ast.Module(body=[f], type_ignores=[])),
                       str(source), "exec")
        space = {"_voz_stt_local": S}
        exec(code, space)
        cls.route = staticmethod(space["_stt_local_wav"])

    def handler(self, *, origin=True, pairs=None, raw=None, proxy=False):
        headers = Message()
        if pairs is None:
            pairs = [("Host", "127.0.0.1:8742"), ("Origin", "http://127.0.0.1:8742"),
                     ("Sec-Fetch-Site", "same-origin"), ("Content-Type", "audio/wav"),
                     ("X-Hexelion-STT-Command", S.COMMAND),
                     ("Content-Length", str(len(self.wav)))]
        for k, v in pairs: headers.add_header(k, v)
        h = SimpleNamespace(headers=headers, rfile=io.BytesIO(self.wav if raw is None else raw),
                            close_connection=False)
        h._nodo_local_autorizado = lambda: origin
        h._tailnet_proxy_request = lambda: proxy
        h._json = lambda status, data: (status, data)
        return h

    def setUp(self): self.wav = fixture_wav()

    def test_route_validates_origin_before_transcription(self):
        for kwargs in ({"origin":False}, {"proxy":True},
                       {"pairs":[("Host","127.0.0.1:8742"),
                                 ("Origin","http://127.0.0.1:8742"),
                                 ("Host","localhost:8742"), ("Content-Type","audio/wav"),
                                 ("Content-Length",str(len(self.wav))),
                                 ("X-Hexelion-STT-Command",S.COMMAND)]}):
            with self.subTest(kwargs=kwargs), patch.object(S,"transcribe_once") as infer:
                h=self.handler(**kwargs)
                status,data=self.route(h)
                self.assertEqual((status,data["cause"]),(403,"local_origin_required"))
                self.assertTrue(h.close_connection)
                infer.assert_not_called()

    def test_route_rejects_wrong_command_type_and_payload(self):
        good=[("Host","127.0.0.1:8742"),("Origin","http://127.0.0.1:8742"),
              ("Sec-Fetch-Site","same-origin"),("Content-Type","audio/wav"),
              ("X-Hexelion-STT-Command",S.COMMAND),("Content-Length",str(len(self.wav)))]
        variants=[
            [(k,"browser-recognize" if k=="X-Hexelion-STT-Command" else v) for k,v in good],
            [(k,"application/json" if k=="Content-Type" else v) for k,v in good],
            [(k,str(S.MAX_WAV_BYTES+1) if k=="Content-Length" else v) for k,v in good],
            good+[("Transfer-Encoding","chunked")],
            good+[("X-Forwarded-For","127.0.0.1")],
        ]
        with patch.object(S,"transcribe_once") as infer:
            for pairs in variants:
                with self.subTest(headers=pairs):
                    status,_=self.route(self.handler(pairs=pairs))
                    self.assertIn(status,(400,403,415))
            infer.assert_not_called()

    def test_route_passes_one_valid_wav_to_existing_engine(self):
        expected={"state":"LOCAL_TRANSCRIPT_ONLY","text":"hola","cause":"not_authenticated_brain_reply"}
        with patch.object(S,"transcribe_once",return_value=expected) as infer:
            status,resp=self.route(self.handler())
            self.assertEqual(status,200)
            self.assertEqual(resp,expected)
            infer.assert_called_once_with({"command":S.COMMAND},self.wav,local_origin_verified=True)

    def test_route_thermal_hold_is_no_data_not_text(self):
        with patch.object(S,"transcribe_once",side_effect=S.STTUnavailable("beelink_cpu_thermal_hold")) as infer:
            status,resp=self.route(self.handler())
            self.assertEqual((status,resp),(503,{"state":"NO_DATA","cause":"beelink_cpu_thermal_hold"}))
            infer.assert_called_once()
