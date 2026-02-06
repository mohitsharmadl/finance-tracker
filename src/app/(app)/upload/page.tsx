"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Upload, FileText, X, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";

type DocumentType = "BANK_STATEMENT" | "CREDIT_CARD" | "TRADING_PNL" | "RECEIPT";

interface FileItem {
  file: File;
  documentType: DocumentType;
  status: "pending" | "uploading" | "processing" | "completed" | "failed";
  progress: number;
  error?: string;
}

export default function UploadPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [defaultType, setDefaultType] = useState<DocumentType>("BANK_STATEMENT");

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const newFiles: FileItem[] = acceptedFiles.map((file) => ({
        file,
        documentType: defaultType,
        status: "pending",
        progress: 0,
      }));
      setFiles((prev) => [...prev, ...newFiles]);
    },
    [defaultType]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/*": [".png", ".jpg", ".jpeg", ".webp"],
      "text/csv": [".csv"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
    },
  });

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const updateFileType = (index: number, type: DocumentType) => {
    setFiles((prev) =>
      prev.map((f, i) => (i === index ? { ...f, documentType: type } : f))
    );
  };

  const uploadFile = async (index: number) => {
    const fileItem = files[index];
    setFiles((prev) =>
      prev.map((f, i) =>
        i === index ? { ...f, status: "uploading", progress: 30 } : f
      )
    );

    try {
      const formData = new FormData();
      formData.append("file", fileItem.file);
      formData.append("documentType", fileItem.documentType);

      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.error || "Upload failed");
      }

      setFiles((prev) =>
        prev.map((f, i) =>
          i === index ? { ...f, status: "processing", progress: 70 } : f
        )
      );

      // Poll for completion
      const { document } = await res.json();
      pollStatus(index, document.id);
    } catch (err) {
      setFiles((prev) =>
        prev.map((f, i) =>
          i === index
            ? {
                ...f,
                status: "failed",
                error: err instanceof Error ? err.message : "Upload failed",
              }
            : f
        )
      );
    }
  };

  const pollStatus = async (index: number, documentId: string) => {
    const maxAttempts = 60;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 2000));

      const res = await fetch("/api/documents");
      if (!res.ok) continue;

      const docs = await res.json();
      const doc = docs.find((d: { id: string }) => d.id === documentId);

      if (doc?.status === "COMPLETED") {
        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === index ? { ...f, status: "completed", progress: 100 } : f
          )
        );
        toast.success(`${files[index].file.name} processed successfully`);
        return;
      }

      if (doc?.status === "FAILED") {
        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === index
              ? { ...f, status: "failed", error: doc.errorMessage || "Processing failed" }
              : f
          )
        );
        toast.error(`Failed to process ${files[index].file.name}`);
        return;
      }

      setFiles((prev) =>
        prev.map((f, idx) =>
          idx === index
            ? { ...f, progress: Math.min(70 + i, 95) }
            : f
        )
      );
    }
  };

  const uploadAll = async () => {
    const pending = files
      .map((f, i) => ({ ...f, index: i }))
      .filter((f) => f.status === "pending");

    for (const f of pending) {
      await uploadFile(f.index);
    }
  };

  const pendingCount = files.filter((f) => f.status === "pending").length;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Upload Documents</h1>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Document Type</CardTitle>
          </CardHeader>
          <CardContent>
            <Select
              value={defaultType}
              onValueChange={(v) => setDefaultType(v as DocumentType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="BANK_STATEMENT">Bank Statement</SelectItem>
                <SelectItem value="CREDIT_CARD">Credit Card Statement</SelectItem>
                <SelectItem value="TRADING_PNL">Trading PnL</SelectItem>
                <SelectItem value="RECEIPT">Receipt</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div
              {...getRootProps()}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
                isDragActive
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/25 hover:border-primary/50"
              }`}
            >
              <input {...getInputProps()} />
              <Upload className="mb-4 h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {isDragActive
                  ? "Drop files here..."
                  : "Drag & drop files or click to browse"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                PDF, Images, CSV, Excel
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {files.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>File Queue ({files.length})</CardTitle>
            {pendingCount > 0 && (
              <Button onClick={uploadAll}>Upload All ({pendingCount})</Button>
            )}
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {files.map((fileItem, index) => (
                <div
                  key={index}
                  className="flex items-center gap-4 rounded-lg border p-3"
                >
                  <FileText className="h-8 w-8 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {fileItem.file.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {(fileItem.file.size / 1024).toFixed(1)} KB
                    </p>
                    {(fileItem.status === "uploading" ||
                      fileItem.status === "processing") && (
                      <Progress value={fileItem.progress} className="mt-1 h-1" />
                    )}
                    {fileItem.error && (
                      <p className="mt-1 text-xs text-destructive">
                        {fileItem.error}
                      </p>
                    )}
                  </div>

                  {fileItem.status === "pending" && (
                    <Select
                      value={fileItem.documentType}
                      onValueChange={(v) =>
                        updateFileType(index, v as DocumentType)
                      }
                    >
                      <SelectTrigger className="w-40">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="BANK_STATEMENT">Bank Statement</SelectItem>
                        <SelectItem value="CREDIT_CARD">Credit Card</SelectItem>
                        <SelectItem value="TRADING_PNL">Trading PnL</SelectItem>
                        <SelectItem value="RECEIPT">Receipt</SelectItem>
                      </SelectContent>
                    </Select>
                  )}

                  <StatusBadge status={fileItem.status} />

                  {fileItem.status === "pending" && (
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        onClick={() => uploadFile(index)}
                      >
                        Upload
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => removeFile(index)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: FileItem["status"] }) {
  switch (status) {
    case "uploading":
      return (
        <Badge variant="secondary" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin" /> Uploading
        </Badge>
      );
    case "processing":
      return (
        <Badge variant="secondary" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin" /> Processing
        </Badge>
      );
    case "completed":
      return (
        <Badge className="gap-1 bg-green-600">
          <CheckCircle className="h-3 w-3" /> Done
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="destructive" className="gap-1">
          <AlertCircle className="h-3 w-3" /> Failed
        </Badge>
      );
    default:
      return null;
  }
}
