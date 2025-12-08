"use client";

import { useRef, useState } from "react";

interface ImageUploadProps {
  label: string;
  value: File | null;
  onChange: (file: File | null) => void;
  preview?: string | null;
}

export default function ImageUpload({ label, onChange, preview }: ImageUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(preview || null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    onChange(file);

    if (file) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }
  };

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(null);
    setPreviewUrl(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  return (
    <div className="w-full">
      <label className="block text-sm text-gray-400 mb-2">{label}</label>
      <div
        onClick={handleClick}
        className="relative bg-dark-elevated border-2 border-dashed border-dark-border rounded-2xl p-6 flex flex-col items-center justify-center cursor-pointer hover:border-accent-cyan/50 transition-colors min-h-[160px]"
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          onChange={handleChange}
          className="hidden"
        />

        {previewUrl ? (
          <>
            <img
              src={previewUrl}
              alt="Product preview"
              className="max-h-32 rounded-xl object-contain"
            />
            <button
              onClick={handleRemove}
              className="absolute top-3 right-3 w-8 h-8 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </>
        ) : (
          <>
            <div className="w-12 h-12 rounded-full bg-dark-card flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-accent-cyan" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-gray-400 text-sm text-center">
              Tap to upload product image
            </p>
            <p className="text-gray-500 text-xs mt-1">PNG, JPG up to 10MB</p>
          </>
        )}
      </div>
    </div>
  );
}
