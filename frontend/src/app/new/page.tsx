"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import ImageUpload from "@/components/ui/ImageUpload";
import { getApiBase } from "@/lib/api";

const providerOptions = [
  { value: "defapi.org|defapi-sora-2", label: "Sora 2", sublabel: "$0.10/15s" },
  { value: "kie.ai|veo-3.1-fast", label: "Kie.ai Veo 3.1 Fast", sublabel: "$0.40/8s" },
  { value: "kie.ai|veo-3.1-quality", label: "Kie.ai Veo 3.1 Quality", sublabel: "$2.00/8s" },
  { value: "kie.ai|sora-2", label: "Kie.ai Sora 2", sublabel: "$0.15/8s" },
  { value: "defapi.org|defapi-veo-3.1", label: "defapi.org Veo 3.1", sublabel: "$0.50/8s" },
];

const strategyOptions = [
  { value: "segments", label: "Segments", sublabel: "Each scene separately" },
  { value: "seamless", label: "Seamless", sublabel: "Full video with extend" },
];

const variantOptions = [
  { value: "1", label: "1 Variant" },
  { value: "2", label: "2 Variants" },
  { value: "3", label: "3 Variants" },
  { value: "5", label: "5 Variants" },
  { value: "10", label: "10 Variants" },
];

export default function NewSessionPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  // Form state
  const [tiktokUrl, setTiktokUrl] = useState("");
  const [productName, setProductName] = useState("");
  const [productImage, setProductImage] = useState<File | null>(null);
  const [providerModel, setProviderModel] = useState("defapi.org|defapi-sora-2");
  const [strategy, setStrategy] = useState("segments");
  const [numVariants, setNumVariants] = useState("1");

  // Cost estimation
  const selectedOption = providerOptions.find((o) => o.value === providerModel);
  const costPer8s = parseFloat(selectedOption?.sublabel?.replace("$", "").replace("/8s", "") || "0.40");
  const estimatedScenes = 4; // Assume 4 scenes average
  const estimatedCost = costPer8s * estimatedScenes * parseInt(numVariants);

  const handleSubmit = async () => {
    if (!tiktokUrl || !productName) {
      alert("Please fill in TikTok URL and Product Name");
      return;
    }

    setIsLoading(true);

    try {
      const [provider, model] = providerModel.split("|");

      // Create session
      const response = await fetch(`${getApiBase()}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tiktok_url: tiktokUrl,
          product_name: productName,
          num_variants: parseInt(numVariants),
          provider,
          model,
          strategy,
        }),
      });

      if (!response.ok) throw new Error("Failed to create session");

      const session = await response.json();

      // Upload image if provided
      if (productImage) {
        const formData = new FormData();
        formData.append("file", productImage);

        await fetch(`${getApiBase()}/sessions/${session.session_id}/image`, {
          method: "POST",
          body: formData,
        });
      }

      // Start generation
      await fetch(`${getApiBase()}/sessions/${session.session_id}/generate`, {
        method: "POST",
      });

      // Navigate to session page
      router.push(`/session/${session.session_id}`);
    } catch {
      alert("Failed to start generation. Is the backend running?");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="px-4 pt-6 pb-8">
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
        <h1 className="text-xl font-bold">New Video Clone</h1>
      </div>

      {/* Form */}
      <div className="space-y-5">
        {/* TikTok URL */}
        <Input
          label="TikTok Video URL"
          placeholder="https://www.tiktok.com/@user/video/..."
          value={tiktokUrl}
          onChange={setTiktokUrl}
          type="url"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          }
        />

        {/* Product Name */}
        <Input
          label="Exact Product Name"
          placeholder="e.g. Philips OneBlade Pro"
          value={productName}
          onChange={setProductName}
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          }
        />

        {/* Product Image */}
        <ImageUpload
          label="Product Reference Image"
          value={productImage}
          onChange={setProductImage}
        />

        {/* Provider & Model */}
        <Select
          label="Provider & Model"
          options={providerOptions}
          value={providerModel}
          onChange={setProviderModel}
        />

        {/* Strategy */}
        <Select
          label="Generation Strategy"
          options={strategyOptions}
          value={strategy}
          onChange={setStrategy}
        />

        {/* Variants */}
        <Select
          label="Number of Variants"
          options={variantOptions}
          value={numVariants}
          onChange={setNumVariants}
        />

        {/* Cost Estimate Card */}
        <Card className="bg-dark-elevated">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Estimated Cost</p>
              <p className="text-2xl font-bold text-accent-cyan">
                ${estimatedCost.toFixed(2)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-gray-400 text-sm">~{estimatedScenes} scenes × {numVariants} variants</p>
              <p className="text-gray-500 text-xs">${costPer8s.toFixed(2)} per 8s clip</p>
            </div>
          </div>
        </Card>

        {/* Submit Button */}
        <Button
          fullWidth
          size="lg"
          onClick={handleSubmit}
          disabled={isLoading || !tiktokUrl || !productName}
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Starting...
            </span>
          ) : (
            "Start Generation"
          )}
        </Button>
      </div>
    </div>
  );
}
