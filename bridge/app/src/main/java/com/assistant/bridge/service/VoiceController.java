package com.assistant.bridge.service;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Log;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * VoiceController: real on-device STT (wake word + live command sessions)
 * and streaming Urdu text-to-speech for the JARVIS bridge.
 *
 * Session flow (single source of truth for the whole assistant):
 *   1. stt_start_wake("jarvis")      -> mic ON, continuous wake-word listening
 *   2. wake word heard               -> mic STAYS ON, live command capture
 *                                       begins, partials exposed word-by-word
 *   3. user says the execute keyword -> mic OFF, state=execute_ready
 *   4. Python reads stt_status, may edit via stt_set_text, then stt_finish
 *   5. stt_start_wake again for the next session
 *
 * TTS streams sentence-by-sentence: the first sentence starts playing
 * immediately while later sentences are still being synthesized; the
 * client never waits for the whole text. Urdu (ur-PK) is preferred,
 * with ur-IN and hi-IN fallbacks depending on installed voices.
 */
final class VoiceController {

    private static final String TAG = "JARVIS_Voice";
    private static final String[] EXECUTE_KEYWORDS = {
            "execute kro", "execute karo", "execute",
            "chala do", "chalado", "chala dao"
    };
    private static final String DEFAULT_LANGUAGE = "ur-PK";
    private static final long RESTART_MIN_DELAY_MS = 250;

    private final Context context;
    private final Handler main = new Handler(Looper.getMainLooper());

    // Session state: idle | wake | command | execute_ready | error
    private final AtomicReference<String> state = new AtomicReference<>("idle");
    private final AtomicBoolean stopping = new AtomicBoolean(false);
    private volatile String wakeWord = "jarvis";
    private volatile String language = DEFAULT_LANGUAGE;
    private final Object textLock = new Object();
    private StringBuilder commandText = new StringBuilder();
    private String partialPreview = "";
    private String lastError = "";
    private volatile long lastRestartAt = 0L;

    // One-shot recognition (speech_to_text / listen_wake_word) runs on its own
    // thread because SpeechRecognizer must be driven from a Looper thread and
    // the RPC worker thread must stay free to block on the latch.
    private final AtomicBoolean oneShotBusy = new AtomicBoolean(false);

    // TTS engine (lazily created, reused across calls)
    private TextToSpeech tts;
    private boolean ttsReady = false;
    private Locale ttsLanguage = new Locale("ur", "PK");
    private final AtomicInteger ttsRemaining = new AtomicInteger(0);
    private final AtomicBoolean ttsDone = new AtomicBoolean(true);
    private String ttsEngineError = "";

    VoiceController(Context context) {
        this.context = context.getApplicationContext();
    }

    // ------------------------------------------------------------------
    // JSON escaping (shared with other bridge classes in this package)
    // ------------------------------------------------------------------

    static String json(String s) {
        if (s == null) {
            return "\"\"";
        }
        StringBuilder sb = new StringBuilder(s.length() + 8);
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':  sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n");  break;
                case '\r': sb.append("\\r");  break;
                case '\t': sb.append("\\t");  break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
        return sb.toString();
    }

    private static String stateJson(String state, String text, String error) {
        return "{\"ok\":" + (error.isEmpty() ? "true" : "false")
                + ",\"state\":" + json(state)
                + ",\"text\":" + json(text)
                + ",\"error\":" + json(error) + "}";
    }

    // ------------------------------------------------------------------
    // Session control (called from RPC worker threads)
    // ------------------------------------------------------------------

    /** Begin continuous wake-word listening. Mic stays on. */
    String startWake(String word, String lang) {
        if (!hasMicPermission()) {
            state.set("error");
            lastError = "RECORD_AUDIO permission not granted";
            return stateJson("error", "", lastError);
        }
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            state.set("error");
            lastError = "speech recognition not available on this device";
            return stateJson("error", "", lastError);
        }
        this.wakeWord = (word == null || word.isEmpty()) ? "jarvis" : word.toLowerCase();
        this.language = (lang == null || lang.isEmpty()) ? DEFAULT_LANGUAGE : lang;
        synchronized (textLock) {
            commandText = new StringBuilder();
            partialPreview = "";
        }
        stopping.set(false);
        lastError = "";
        state.set("wake");
        main.post(() -> restartRecognition());
        return stateJson("wake", "", "");
    }

    /**
     * Skip the wake phase and begin live command capture directly.
     * Mic stays on until the execute keyword or stt_finish/stt_cancel.
     */
    String startCommand(String lang) {
        if (!hasMicPermission()) {
            state.set("error");
            lastError = "RECORD_AUDIO permission not granted";
            return stateJson("error", "", lastError);
        }
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            state.set("error");
            lastError = "speech recognition not available on this device";
            return stateJson("error", "", lastError);
        }
        this.language = (lang == null || lang.isEmpty()) ? DEFAULT_LANGUAGE : lang;
        synchronized (textLock) {
            commandText = new StringBuilder();
            partialPreview = "";
        }
        stopping.set(false);
        lastError = "";
        state.set("command");
        main.post(() -> restartRecognition());
        return stateJson("command", "", "");
    }

    /**
     * Finalize the session: stop the mic, strip any trailing execute
     * keyword and return the final command text.
     */
    String finish() {
        stopping.set(true);
        main.post(() -> destroyRecognizer());
        String text = currentText();
        String stripped = stripExecuteKeyword(text).trim();
        state.set("idle");
        synchronized (textLock) {
            commandText = new StringBuilder(stripped);
            partialPreview = stripped;
        }
        return "{\"ok\":true,\"state\":\"idle\",\"text\":" + json(stripped) + "}";
    }

    /** Cancel everything: mic off, text discarded. */
    String cancel() {
        stopping.set(true);
        main.post(() -> destroyRecognizer());
        state.set("idle");
        synchronized (textLock) {
            commandText = new StringBuilder();
            partialPreview = "";
        }
        return "{\"ok\":true,\"state\":\"idle\"}";
    }

    /** Replace the accumulated command text (edit support from Python). */
    String setText(String newText) {
        synchronized (textLock) {
            commandText = new StringBuilder(newText == null ? "" : newText);
            partialPreview = newText == null ? "" : newText;
        }
        // If the edited text ends with an execute keyword, the session is
        // ready to execute; otherwise return to live listening.
        if (endsWithExecute(newText)) {
            state.set("execute_ready");
        } else {
            if ("idle".equals(state.get()) || "execute_ready".equals(state.get())) {
                state.set("command");
                main.post(() -> {
                    if (!stopping.get()) {
                        restartRecognition();
                    }
                });
            }
        }
        return status();
    }

    /** Current session status with live word-by-word preview. */
    String status() {
        String text;
        synchronized (textLock) {
            text = commandText.toString();
            if (!partialPreview.isEmpty()) {
                if (text.isEmpty()) {
                    text = partialPreview;
                } else if (!partialPreview.equals(text)) {
                    text = (text + " " + partialPreview).trim();
                }
            }
        }
        String st = state.get();
        String err = "error".equals(st) ? lastError : "";
        return stateJson(st, text, err);
    }

    // ------------------------------------------------------------------
    // Recognition machinery (main thread only)
    // ------------------------------------------------------------------

    private SpeechRecognizer recognizer;
    private volatile SpeechRecognizer oneShotRecognizer;

    private void destroyOneShot() {
        try {
            if (oneShotRecognizer != null) {
                oneShotRecognizer.destroy();
                oneShotRecognizer = null;
            }
        } catch (Exception e) {
            Log.w(TAG, "destroyOneShot failed: " + e.getMessage());
        }
    }

    private void destroyRecognizer() {
        try {
            if (recognizer != null) {
                recognizer.destroy();
                recognizer = null;
            }
        } catch (Exception e) {
            Log.w(TAG, "destroyRecognizer failed: " + e.getMessage());
        }
    }

    private void restartRecognition() {
        if (stopping.get()) {
            return;
        }
        long now = System.currentTimeMillis();
        if (now - lastRestartAt < RESTART_MIN_DELAY_MS) {
            main.postDelayed(() -> {
                if (!stopping.get()) {
                    restartRecognition();
                }
            }, RESTART_MIN_DELAY_MS);
            return;
        }
        lastRestartAt = now;
        destroyRecognizer();
        try {
            recognizer = SpeechRecognizer.createSpeechRecognizer(context);
            recognizer.setRecognitionListener(sessionListener);
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, language);
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
            intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
            recognizer.startListening(intent);
        } catch (Exception e) {
            Log.e(TAG, "startListening failed", e);
            state.set("error");
            lastError = "failed to start listening: " + e.getMessage();
        }
    }

    private final RecognitionListener sessionListener = new RecognitionListener() {
        @Override public void onReadyForSpeech(Bundle params) { }
        @Override public void onBeginningOfSpeech() { }
        @Override public void onRmsChanged(float rmsdB) { }
        @Override public void onBufferReceived(byte[] buffer) { }
        @Override public void onEndOfSpeech() { }
        @Override public void onEvent(int eventType, Bundle params) { }

        @Override
        public void onError(int error) {
            if (stopping.get()) {
                return;
            }
            if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
                state.set("error");
                lastError = "RECORD_AUDIO permission not granted";
                return;
            }
            // NO_MATCH(1), SPEECH_TIMEOUT(6), RECOGNIZER_BUSY(8) and CLIENT(5)
            // are normal in continuous mode: restart and keep the mic alive.
            main.postDelayed(() -> {
                if (!stopping.get()) {
                    restartRecognition();
                }
            }, 300);
        }

        @Override
        public void onPartialResults(Bundle partialResults) {
            String partial = joinResults(partialResults);
            if (partial.isEmpty()) {
                return;
            }
            synchronized (textLock) {
                partialPreview = partial;
            }
            String st = state.get();
            if ("wake".equals(st) && containsWakeWord(partial)) {
                // Wake word heard mid-speech: switch to command capture
                // immediately; the mic stays on.
                synchronized (textLock) {
                    commandText = new StringBuilder();
                    partialPreview = "";
                }
                state.set("command");
            }
        }

        @Override
        public void onResults(Bundle results) {
            String text = joinResults(results);
            String st = state.get();
            if ("wake".equals(st)) {
                if (containsWakeWord(text)) {
                    synchronized (textLock) {
                        commandText = new StringBuilder();
                        partialPreview = "";
                    }
                    state.set("command");
                }
                if (!stopping.get()) {
                    restartRecognition();
                }
                return;
            }
            if ("command".equals(st)) {
                synchronized (textLock) {
                    if (!text.isEmpty()) {
                        if (commandText.length() > 0) {
                            commandText.append(' ');
                        }
                        commandText.append(text);
                    }
                    partialPreview = "";
                }
                String full = currentText();
                if (endsWithExecute(full)) {
                    // User finished the command: mic OFF, text final.
                    stopping.set(true);
                    destroyRecognizer();
                    synchronized (textLock) {
                        String stripped = stripExecuteKeyword(currentText()).trim();
                        commandText = new StringBuilder(stripped);
                    }
                    state.set("execute_ready");
                    return;
                }
                if (!stopping.get()) {
                    restartRecognition();
                }
            }
        }
    };

    private String currentText() {
        synchronized (textLock) {
            return commandText.toString();
        }
    }

    private static String joinResults(Bundle bundle) {
        if (bundle == null) {
            return "";
        }
        ArrayList<String> list = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (list == null || list.isEmpty()) {
            return "";
        }
        return list.get(0) == null ? "" : list.get(0).trim();
    }

    private boolean containsWakeWord(String text) {
        if (text == null) {
            return false;
        }
        return text.toLowerCase().contains(wakeWord);
    }

    private static boolean endsWithExecute(String text) {
        return !stripExecuteKeyword(text).equals(text == null ? "" : text);
    }

    private static String stripExecuteKeyword(String text) {
        if (text == null || text.isEmpty()) {
            return "";
        }
        String lower = text.toLowerCase().trim();
        for (String kw : EXECUTE_KEYWORDS) {
            if (lower.endsWith(kw)) {
                return text.trim().substring(0, text.trim().length() - kw.length());
            }
            if (lower.contains(kw + " ")) {
                int idx = lower.indexOf(kw + " ");
                return text.substring(0, idx);
            }
        }
        return text;
    }

    // ------------------------------------------------------------------
    // Blocking one-shot methods (legacy Python API compatibility)
    // ------------------------------------------------------------------

    /**
     * One-shot recognition with timeout. Blocks the calling RPC thread.
     * Returns {"ok":true,"text":...,"confidence":...} or an honest error.
     */
    String recognizeOnce(String lang, double timeoutSeconds) {
        if (!hasMicPermission()) {
            return "{\"ok\":false,\"error\":\"RECORD_AUDIO permission not granted\"}";
        }
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            return "{\"ok\":false,\"error\":\"speech recognition not available\"}";
        }
        if (!oneShotBusy.compareAndSet(false, true)) {
            return "{\"ok\":false,\"error\":\"another recognition is already running\"}";
        }
        final String useLang = (lang == null || lang.isEmpty()) ? DEFAULT_LANGUAGE : lang;
        final long timeoutMs = timeoutSeconds <= 0 ? 10000L : (long) (timeoutSeconds * 1000.0);
        final CountDownLatch latch = new CountDownLatch(1);
        final AtomicReference<String> textRef = new AtomicReference<>("");
        final AtomicReference<Float> confRef = new AtomicReference<>(0.0f);
        final AtomicReference<String> errRef = new AtomicReference<>("");
        main.post(() -> {
            SpeechRecognizer r;
            try {
                r = SpeechRecognizer.createSpeechRecognizer(context);
                oneShotRecognizer = r;
            } catch (Exception e) {
                errRef.set("failed to create recognizer: " + e.getMessage());
                latch.countDown();
                return;
            }
            r.setRecognitionListener(new RecognitionListener() {
                @Override public void onReadyForSpeech(Bundle p) { }
                @Override public void onBeginningOfSpeech() { }
                @Override public void onRmsChanged(float v) { }
                @Override public void onBufferReceived(byte[] b) { }
                @Override public void onEndOfSpeech() { }
                @Override public void onEvent(int t, Bundle p) { }
                @Override public void onPartialResults(Bundle p) { }
                @Override
                public void onError(int error) {
                    errRef.set("recognition error " + error);
                    latch.countDown();
                    try { r.destroy(); } catch (Exception ignored) { }
                }
                @Override
                public void onResults(Bundle results) {
                    ArrayList<String> list = results == null ? null
                            : results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    float[] conf = results == null ? null
                            : results.getFloatArray(SpeechRecognizer.CONFIDENCE_SCORES);
                    if (list != null && !list.isEmpty()) {
                        textRef.set(list.get(0));
                    }
                    if (conf != null && conf.length > 0) {
                        confRef.set(conf[0]);
                    }
                    latch.countDown();
                    try { r.destroy(); } catch (Exception ignored) { }
                }
            });
            try {
                Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, useLang);
                intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
                r.startListening(intent);
            } catch (Exception e) {
                errRef.set("failed to start listening: " + e.getMessage());
                latch.countDown();
                try { r.destroy(); } catch (Exception ignored) { }
            }
        });
        boolean completed;
        try {
            completed = latch.await(timeoutMs, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            completed = false;
        }
        oneShotBusy.set(false);
        if (!completed) {
            main.post(() -> destroyOneShot());
            return "{\"ok\":false,\"error\":\"recognition timed out after "
                    + timeoutMs + " ms\"}";
        }
        if (!errRef.get().isEmpty()) {
            return "{\"ok\":false,\"error\":" + json(errRef.get()) + "}";
        }
        return "{\"ok\":true,\"text\":" + json(textRef.get())
                + ",\"confidence\":" + confRef.get() + "}";
    }

    /**
     * Block until the wake word is heard or the timeout expires.
     * Returns {"ok":true,"detected":true,...} or an honest error/timeout.
     */
    String listenWakeBlocking(String word, double timeoutSeconds) {
        if (!hasMicPermission()) {
            return "{\"ok\":false,\"detected\":false,\"error\":\"RECORD_AUDIO permission not granted\"}";
        }
        String target = (word == null || word.isEmpty()) ? "jarvis" : word.toLowerCase();
        long deadline = System.currentTimeMillis()
                + (timeoutSeconds <= 0 ? 30000L : (long) (timeoutSeconds * 1000.0));
        while (System.currentTimeMillis() < deadline && !Thread.currentThread().isInterrupted()) {
            long remaining = deadline - System.currentTimeMillis();
            String result = recognizeOnce(language, Math.max(1.0, remaining / 1000.0));
            if (result.contains("\"ok\":true") && result.toLowerCase().contains(target)) {
                return "{\"ok\":true,\"detected\":true,\"confidence\":1.0}";
            }
            if (result.contains("\"ok\":false")
                    && !result.contains("timed out")) {
                return "{\"ok\":false,\"detected\":false,\"error\":"
                        + json(extractJsonError(result)) + "}";
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return "{\"ok\":false,\"detected\":false,\"error\":\"interrupted\"}";
            }
        }
        return "{\"ok\":false,\"detected\":false,\"error\":\"wake word timeout\"}";
    }

    private static String extractJsonError(String json) {
        int idx = json.indexOf("\"error\":\"");
        if (idx < 0) {
            return "unknown error";
        }
        int start = idx + 9;
        int end = json.indexOf('"', start);
        return end > start ? json.substring(start, end) : "unknown error";
    }

    private boolean hasMicPermission() {
        return context.checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED;
    }

    // ------------------------------------------------------------------
    // Streaming TTS (sentence-level: first sentence plays immediately)
    // ------------------------------------------------------------------

    private synchronized void ensureTts() {
        if (tts != null) {
            return;
        }
        ttsReady = false;
        final CountDownLatch ready = new CountDownLatch(1);
        tts = new TextToSpeech(context, status -> {
            ttsReady = status == TextToSpeech.SUCCESS;
            if (ttsReady) {
                tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override
                    public void onStart(String utteranceId) {
                        ttsDone.set(false);
                    }

                    @Override
                    public void onDone(String utteranceId) {
                        if (ttsRemaining.decrementAndGet() <= 0) {
                            ttsDone.set(true);
                        }
                    }

                    @Override
                    public void onError(String utteranceId) {
                        if (ttsRemaining.decrementAndGet() <= 0) {
                            ttsDone.set(true);
                        }
                    }
                });
            } else {
                ttsEngineError = "TTS engine init failed with status " + status;
            }
            ready.countDown();
        });
        try {
            ready.await(5, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    /**
     * Speak text with sentence-level streaming. The first sentence is
     * queued for immediate playback; remaining sentences are appended to
     * the TTS queue so playback begins from the first byte/utterance
     * without waiting for the whole file.
     */
    String speak(String text, String lang) {
        if (text == null || text.isEmpty()) {
            return "{\"ok\":false,\"error\":\"empty text\"}";
        }
        ensureTts();
        if (tts == null || !ttsReady) {
            return "{\"ok\":false,\"error\":" + json(
                    ttsEngineError.isEmpty() ? "TTS engine not ready" : ttsEngineError) + "}";
        }
        Locale loc = localeFor(lang);
        ttsLanguage = loc;
        int result = tts.setLanguage(loc);
        if (result == TextToSpeech.LANG_MISSING_DATA
                || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            // Honest fallback chain: ur-PK -> ur-IN -> hi-IN -> en-US
            if ("ur".equals(loc.getLanguage())) {
                loc = new Locale("ur", "IN");
                result = tts.setLanguage(loc);
                if (result == TextToSpeech.LANG_MISSING_DATA
                        || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                    loc = new Locale("hi", "IN");
                    result = tts.setLanguage(loc);
                    if (result == TextToSpeech.LANG_MISSING_DATA
                            || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                        loc = Locale.US;
                        tts.setLanguage(loc);
                    }
                }
            } else if ("hi".equals(loc.getLanguage())) {
                loc = Locale.US;
                tts.setLanguage(loc);
            }
            ttsLanguage = loc;
        }
        List<String> sentences = splitSentences(text);
        ttsRemaining.set(sentences.size());
        ttsDone.set(false);
        int queued = 0;
        for (int i = 0; i < sentences.size(); i++) {
            Bundle params = new Bundle();
            params.putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f);
            int r = tts.speak(sentences.get(i), TextToSpeech.QUEUE_ADD, params, "jarvis_" + i);
            if (r == TextToSpeech.SUCCESS) {
                queued++;
            }
        }
        if (queued == 0) {
            ttsDone.set(true);
            return "{\"ok\":false,\"error\":\"TTS rejected all sentences\"}";
        }
        return "{\"ok\":true,\"queued\":" + queued
                + ",\"language\":" + json(ttsLanguage.toLanguageTag())
                + ",\"streaming\":true}";
    }

    String ttsStop() {
        if (tts != null) {
            tts.stop();
        }
        ttsRemaining.set(0);
        ttsDone.set(true);
        return "{\"ok\":true}";
    }

    String ttsStatus() {
        return "{\"ok\":true,\"speaking\":" + !ttsDone.get()
                + ",\"done\":" + ttsDone.get()
                + ",\"language\":" + json(ttsLanguage.toLanguageTag())
                + ",\"ready\":" + (tts != null && ttsReady) + "}";
    }

    private static Locale localeFor(String lang) {
        if (lang == null || lang.isEmpty()) {
            return new Locale("ur", "PK");
        }
        String[] parts = lang.replace('_', '-').split("-", 2);
        if (parts.length == 2) {
            return new Locale(parts[0], parts[1]);
        }
        return new Locale(parts[0]);
    }

    /** Split text into sentences; Urdu full stop (U+06D4) included. */
    private static List<String> splitSentences(String text) {
        List<String> out = new ArrayList<>();
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            sb.append(c);
            if (c == '.' || c == '!' || c == '?' || c == '\n'
                    || c == '\u061F' /* Arabic ? */ || c == '\u06D4' /* Urdu . */) {
                String s = sb.toString().trim();
                if (!s.isEmpty()) {
                    out.add(s);
                }
                sb.setLength(0);
            }
        }
        String tail = sb.toString().trim();
        if (!tail.isEmpty()) {
            out.add(tail);
        }
        if (out.isEmpty()) {
            out.add(text.trim());
        }
        return out;
    }

    /** Release all resources when the foreground service dies. */
    void shutdown() {
        stopping.set(true);
        main.post(() -> {
            destroyRecognizer();
            if (tts != null) {
                try {
                    tts.stop();
                    tts.shutdown();
                } catch (Exception ignored) {
                }
                tts = null;
                ttsReady = false;
            }
        });
        state.set("idle");
    }
}
