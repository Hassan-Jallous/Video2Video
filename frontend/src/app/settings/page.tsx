"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { getApiBase } from "@/lib/api";

type KeyStatus = "untested" | "validating" | "valid" | "invalid";

interface KeyState {
  value: string;
  status: KeyStatus;
  message: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);

  // API Keys state
  const [geminiKey, setGeminiKey] = useState<KeyState>({
    value: "",
    status: "untested",
    message: "",
  });
  const [kieAiKey, setKieAiKey] = useState<KeyState>({
    value: "",
    status: "untested",
    message: "",
  });
  const [defapiKey, setDefapiKey] = useState<KeyState>({
    value: "",
    status: "untested",
    message: "",
  });
  const [keysChanged, setKeysChanged] = useState(false);

  // Prompt templates state
  const [sora2Prompt, setSora2Prompt] = useState("");
  const [veo3Prompt, setVeo3Prompt] = useState("");
  const [originalSora2, setOriginalSora2] = useState("");
  const [originalVeo3, setOriginalVeo3] = useState("");
  const [expandedPrompt, setExpandedPrompt] = useState<string | null>(null);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await fetch(`${getApiBase()}/settings`);
      if (response.ok) {
        const data = await response.json();
        // Update key status indicators
        setGeminiKey((prev) => ({
          ...prev,
          status: data.gemini_key_set ? "valid" : "untested",
          message: data.gemini_key_set ? "Key is set" : "",
        }));
        setKieAiKey((prev) => ({
          ...prev,
          status: data.kie_ai_key_set ? "valid" : "untested",
          message: data.kie_ai_key_set ? "Key is set" : "",
        }));
        setDefapiKey((prev) => ({
          ...prev,
          status: data.defapi_key_set ? "valid" : "untested",
          message: data.defapi_key_set ? "Key is set" : "",
        }));
        // Load prompts
        setSora2Prompt(data.sora_2_prompt || "");
        setVeo3Prompt(data.veo_3_prompt || "");
        setOriginalSora2(data.sora_2_prompt || "");
        setOriginalVeo3(data.veo_3_prompt || "");
      }
    } catch (error) {
      console.error("Failed to load settings:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const validateKey = async (
    keyType: "gemini" | "kie_ai" | "defapi",
    keyValue: string,
    setter: React.Dispatch<React.SetStateAction<KeyState>>
  ) => {
    if (!keyValue || keyValue.length < 10) {
      setter((prev) => ({
        ...prev,
        status: "invalid",
        message: "Key is too short",
      }));
      return;
    }

    setter((prev) => ({ ...prev, status: "validating", message: "Validating..." }));

    try {
      const response = await fetch(`${getApiBase()}/settings/validate-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key_type: keyType, key_value: keyValue }),
      });

      const data = await response.json();
      setter({
        value: keyValue,
        status: data.is_valid ? "valid" : "invalid",
        message: data.message,
      });
    } catch {
      setter((prev) => ({
        ...prev,
        status: "invalid",
        message: "Validation failed",
      }));
    }
  };

  const saveKeys = async () => {
    const updates: Record<string, string> = {};
    if (geminiKey.value) updates.gemini_key = geminiKey.value;
    if (kieAiKey.value) updates.kie_ai_key = kieAiKey.value;
    if (defapiKey.value) updates.defapi_key = defapiKey.value;

    try {
      const response = await fetch(`${getApiBase()}/settings/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (response.ok) {
        setKeysChanged(false);
        // Clear input values and update status to show keys are saved
        if (geminiKey.value) {
          setGeminiKey({ value: "", status: "valid", message: "Key is set" });
        }
        if (kieAiKey.value) {
          setKieAiKey({ value: "", status: "valid", message: "Key is set" });
        }
        if (defapiKey.value) {
          setDefapiKey({ value: "", status: "valid", message: "Key is set" });
        }
      }
    } catch (error) {
      console.error("Failed to save keys:", error);
    }
  };

  const savePrompt = async (type: "sora_2" | "veo_3") => {
    const updates: Record<string, string> = {};
    if (type === "sora_2") {
      updates.sora_2_prompt = sora2Prompt;
    } else {
      updates.veo_3_prompt = veo3Prompt;
    }

    try {
      const response = await fetch(`${getApiBase()}/settings/prompts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (response.ok) {
        if (type === "sora_2") {
          setOriginalSora2(sora2Prompt);
        } else {
          setOriginalVeo3(veo3Prompt);
        }
      }
    } catch (error) {
      console.error("Failed to save prompt:", error);
    }
  };

  const resetPrompts = async () => {
    try {
      const response = await fetch(`${getApiBase()}/settings/prompts/reset`, {
        method: "POST",
      });

      if (response.ok) {
        loadSettings();
      }
    } catch (error) {
      console.error("Failed to reset prompts:", error);
    }
  };

  const getStatusIcon = (status: KeyStatus) => {
    switch (status) {
      case "valid":
        return (
          <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        );
      case "invalid":
        return (
          <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      case "validating":
        return (
          <svg className="w-5 h-5 text-accent-cyan animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        );
      default:
        return (
          <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
    }
  };

  if (isLoading) {
    return (
      <div className="px-4 pt-6 pb-32 flex items-center justify-center min-h-screen">
        <div className="animate-spin w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="px-4 pt-6 pb-32">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => router.back()}
          className="w-10 h-10 rounded-full bg-dark-card flex items-center justify-center"
        >
          <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="text-xl font-bold">AI Settings</h1>
      </div>

      {/* API Keys Section */}
      <Card className="mb-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-accent-cyan" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          API Keys
        </h2>

        {/* Gemini Key */}
        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">Google Gemini API Key</label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="password"
                placeholder={geminiKey.status === "valid" ? "••••••••••••••••" : "Enter Gemini API key"}
                value={geminiKey.value}
                onChange={(e) => {
                  setGeminiKey((prev) => ({ ...prev, value: e.target.value, status: "untested" }));
                  setKeysChanged(true);
                }}
                className="w-full bg-dark-elevated border border-dark-border rounded-xl py-3 px-4 pr-10 text-white placeholder-gray-500 focus:outline-none focus:border-accent-cyan transition-colors"
              />
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                {getStatusIcon(geminiKey.status)}
              </div>
            </div>
            <button
              onClick={() => validateKey("gemini", geminiKey.value, setGeminiKey)}
              disabled={!geminiKey.value || geminiKey.status === "validating"}
              className="px-4 py-2 bg-dark-elevated border border-dark-border rounded-xl text-sm text-gray-400 hover:text-white hover:border-accent-cyan transition-colors disabled:opacity-50"
            >
              Test
            </button>
          </div>
          {geminiKey.message && (
            <p className={`text-xs mt-1 ${geminiKey.status === "valid" ? "text-green-500" : geminiKey.status === "invalid" ? "text-red-500" : "text-gray-500"}`}>
              {geminiKey.message}
            </p>
          )}
        </div>

        {/* Kie.ai Key */}
        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">Kie.ai API Key</label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="password"
                placeholder={kieAiKey.status === "valid" ? "••••••••••••••••" : "Enter Kie.ai API key"}
                value={kieAiKey.value}
                onChange={(e) => {
                  setKieAiKey((prev) => ({ ...prev, value: e.target.value, status: "untested" }));
                  setKeysChanged(true);
                }}
                className="w-full bg-dark-elevated border border-dark-border rounded-xl py-3 px-4 pr-10 text-white placeholder-gray-500 focus:outline-none focus:border-accent-cyan transition-colors"
              />
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                {getStatusIcon(kieAiKey.status)}
              </div>
            </div>
            <button
              onClick={() => validateKey("kie_ai", kieAiKey.value, setKieAiKey)}
              disabled={!kieAiKey.value || kieAiKey.status === "validating"}
              className="px-4 py-2 bg-dark-elevated border border-dark-border rounded-xl text-sm text-gray-400 hover:text-white hover:border-accent-cyan transition-colors disabled:opacity-50"
            >
              Test
            </button>
          </div>
          {kieAiKey.message && (
            <p className={`text-xs mt-1 ${kieAiKey.status === "valid" ? "text-green-500" : kieAiKey.status === "invalid" ? "text-red-500" : "text-gray-500"}`}>
              {kieAiKey.message}
            </p>
          )}
        </div>

        {/* defapi.org Key */}
        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">defapi.org API Key</label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="password"
                placeholder={defapiKey.status === "valid" ? "••••••••••••••••" : "Enter defapi.org API key"}
                value={defapiKey.value}
                onChange={(e) => {
                  setDefapiKey((prev) => ({ ...prev, value: e.target.value, status: "untested" }));
                  setKeysChanged(true);
                }}
                className="w-full bg-dark-elevated border border-dark-border rounded-xl py-3 px-4 pr-10 text-white placeholder-gray-500 focus:outline-none focus:border-accent-cyan transition-colors"
              />
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                {getStatusIcon(defapiKey.status)}
              </div>
            </div>
            <button
              onClick={() => validateKey("defapi", defapiKey.value, setDefapiKey)}
              disabled={!defapiKey.value || defapiKey.status === "validating"}
              className="px-4 py-2 bg-dark-elevated border border-dark-border rounded-xl text-sm text-gray-400 hover:text-white hover:border-accent-cyan transition-colors disabled:opacity-50"
            >
              Test
            </button>
          </div>
          {defapiKey.message && (
            <p className={`text-xs mt-1 ${defapiKey.status === "valid" ? "text-green-500" : defapiKey.status === "invalid" ? "text-red-500" : "text-gray-500"}`}>
              {defapiKey.message}
            </p>
          )}
        </div>

        {keysChanged && (
          <Button fullWidth onClick={saveKeys}>
            Save API Keys
          </Button>
        )}
      </Card>

      {/* Prompt Templates Section */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <svg className="w-5 h-5 text-accent-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Prompt Templates
          </h2>
          <button
            onClick={resetPrompts}
            className="text-xs text-gray-500 hover:text-accent-cyan transition-colors"
          >
            Reset to defaults
          </button>
        </div>

        {/* Sora 2 Prompt */}
        <div className="mb-4">
          <button
            onClick={() => setExpandedPrompt(expandedPrompt === "sora2" ? null : "sora2")}
            className="w-full flex items-center justify-between p-4 bg-dark-elevated rounded-xl border border-dark-border hover:border-accent-cyan transition-colors"
          >
            <span className="font-medium">Sora 2 System Prompt</span>
            <svg
              className={`w-5 h-5 text-gray-400 transition-transform ${expandedPrompt === "sora2" ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {expandedPrompt === "sora2" && (
            <div className="mt-2 space-y-2">
              <textarea
                value={sora2Prompt}
                onChange={(e) => setSora2Prompt(e.target.value)}
                rows={12}
                className="w-full bg-dark-elevated border border-dark-border rounded-xl py-3 px-4 text-white text-sm font-mono placeholder-gray-500 focus:outline-none focus:border-accent-cyan transition-colors resize-y"
              />
              {sora2Prompt !== originalSora2 && (
                <Button fullWidth onClick={() => savePrompt("sora_2")}>
                  Save Sora 2 Prompt
                </Button>
              )}
            </div>
          )}
        </div>

        {/* Veo 3.1 Prompt */}
        <div>
          <button
            onClick={() => setExpandedPrompt(expandedPrompt === "veo3" ? null : "veo3")}
            className="w-full flex items-center justify-between p-4 bg-dark-elevated rounded-xl border border-dark-border hover:border-accent-cyan transition-colors"
          >
            <span className="font-medium">Veo 3.1 System Prompt</span>
            <svg
              className={`w-5 h-5 text-gray-400 transition-transform ${expandedPrompt === "veo3" ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {expandedPrompt === "veo3" && (
            <div className="mt-2 space-y-2">
              <textarea
                value={veo3Prompt}
                onChange={(e) => setVeo3Prompt(e.target.value)}
                rows={12}
                className="w-full bg-dark-elevated border border-dark-border rounded-xl py-3 px-4 text-white text-sm font-mono placeholder-gray-500 focus:outline-none focus:border-accent-cyan transition-colors resize-y"
              />
              {veo3Prompt !== originalVeo3 && (
                <Button fullWidth onClick={() => savePrompt("veo_3")}>
                  Save Veo 3.1 Prompt
                </Button>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
