"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Loader2,
  RefreshCw,
  Trash2,
  FileText,
} from "lucide-react";
import { format } from "date-fns";
import { toast } from "sonner";

interface Document {
  id: string;
  fileName: string;
  fileType: string;
  documentType: string;
  status: string;
  statementMonth: string | null;
  errorMessage: string | null;
  createdAt: string;
  _count: { transactions: number };
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDocuments = useCallback(async () => {
    const res = await fetch("/api/documents");
    if (res.ok) {
      setDocuments(await res.json());
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Poll for processing documents
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.status === "PENDING" || d.status === "PROCESSING"
    );
    if (!hasProcessing) return;

    const interval = setInterval(fetchDocuments, 3000);
    return () => clearInterval(interval);
  }, [documents, fetchDocuments]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document and all its transactions?")) return;

    const res = await fetch(`/api/documents/${id}`, { method: "DELETE" });
    if (res.ok) {
      toast.success("Document deleted");
      fetchDocuments();
    } else {
      toast.error("Failed to delete document");
    }
  };

  const handleReprocess = async (id: string) => {
    const res = await fetch(`/api/documents/${id}/reprocess`, {
      method: "POST",
    });
    if (res.ok) {
      toast.success("Reprocessing started");
      fetchDocuments();
    } else {
      toast.error("Failed to reprocess document");
    }
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case "PENDING":
        return (
          <Badge variant="secondary" className="gap-1">
            <Clock className="h-3 w-3" /> Pending
          </Badge>
        );
      case "PROCESSING":
        return (
          <Badge variant="secondary" className="gap-1">
            <Loader2 className="h-3 w-3 animate-spin" /> Processing
          </Badge>
        );
      case "COMPLETED":
        return (
          <Badge className="gap-1 bg-green-600">
            <CheckCircle className="h-3 w-3" /> Completed
          </Badge>
        );
      case "FAILED":
        return (
          <Badge variant="destructive" className="gap-1">
            <AlertCircle className="h-3 w-3" /> Failed
          </Badge>
        );
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const docTypeLabel = (type: string) => {
    switch (type) {
      case "BANK_STATEMENT":
        return "Bank Statement";
      case "CREDIT_CARD":
        return "Credit Card";
      case "TRADING_PNL":
        return "Trading PnL";
      case "RECEIPT":
        return "Receipt";
      default:
        return type;
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Documents</h1>

      {documents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="mb-4 h-12 w-12 text-muted-foreground" />
            <p className="text-muted-foreground">No documents uploaded yet</p>
            <Button className="mt-4" onClick={() => (window.location.href = "/upload")}>
              Upload Documents
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Upload History ({documents.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>File Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Transactions</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="max-w-[200px] truncate font-medium">
                      {doc.fileName}
                    </TableCell>
                    <TableCell>{docTypeLabel(doc.documentType)}</TableCell>
                    <TableCell>
                      <div>
                        {statusBadge(doc.status)}
                        {doc.errorMessage && (
                          <p className="mt-1 text-xs text-destructive">
                            {doc.errorMessage}
                          </p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>{doc._count.transactions}</TableCell>
                    <TableCell>
                      {format(new Date(doc.createdAt), "MMM d, yyyy HH:mm")}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleReprocess(doc.id)}
                          disabled={doc.status === "PROCESSING"}
                        >
                          <RefreshCw className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(doc.id)}
                          disabled={doc.status === "PROCESSING"}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
