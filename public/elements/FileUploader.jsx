import React, { useRef, useState } from "react";
import { Upload, CheckCircle2, X } from "lucide-react";

export default function FileUploader({ userEmail }) {
  const inputRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [successOpen, setSuccessOpen] = useState(false);
  const [successText, setSuccessText] = useState("");

  const handleClick = () => {
    if (!loading) inputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (!selectedFiles.length) return;

    setLoading(true);
    setSuccessOpen(false);
    setSuccessText("");

    try {
      const filePromises = selectedFiles.map(
        (file) =>
          new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              const base64Content = String(reader.result).split(",")[1];
              resolve({
                File_name: file.name,
                File_type: file.type || "application/octet-stream",
                File_content: base64Content,
              });
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
          })
      );

      const allFiles = await Promise.all(filePromises);

      const AZURE_LOGIC_APP_URL = "https://prod-23.australiaeast.logic.azure.com:443/workflows/b0f4bc87dc20419c9e228600e5f82173/triggers/When_a_HTTP_request_is_received/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2FWhen_a_HTTP_request_is_received%2Frun&sv=1.0&sig=5NLJQI5qt8S5nQocgeqHFw4533S1QPHZTq9Ygnqf2oI";
      const payload = { Files: allFiles };

      const response = await fetch(AZURE_LOGIC_APP_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => "");
        throw new Error(`Upload failed (${response.status}). ${errorText}`);
      }

      // Success → show success modal (instead of alert)
      const names = allFiles.map((f) => f.File_name).join(", ");
      setSuccessText(`Successfully uploaded ${allFiles.length} file(s): ${names}`);
      setSuccessOpen(true);
    } catch (err) {
      // You can keep an alert for errors, or make an error modal similarly
      console.error("File upload error:", err);
      alert(`❌ Failed to upload files: ${err.message}`);
    } finally {
      setLoading(false);
      // reset input so selecting same files again triggers change
      e.target.value = "";
    }
  };

  return (
    <>
      {/* Hidden input */}
      <input
        ref={inputRef}
        type="file"
        multiple
        style={{ display: "none" }}
        onChange={handleFileChange}
      />

      {/* Floating FAB */}
      <button
        onClick={handleClick}
        title={loading ? "Uploading..." : "Upload Files to Azure"}
        style={{
          position: "fixed",
          bottom: "20px",
          right: "20px",
          width: "56px",
          height: "56px",
          borderRadius: "50%",
          backgroundColor: loading ? "#9ca3af" : "#2563eb",
          border: "none",
          boxShadow: "0 4px 10px rgba(0,0,0,0.3)",
          cursor: loading ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 9999,
          transition: "transform 0.2s ease, background-color 0.2s ease",
        }}
        onMouseEnter={(e) => {
          if (!loading) e.currentTarget.style.transform = "scale(1.1)";
        }}
        onMouseLeave={(e) => {
          if (!loading) e.currentTarget.style.transform = "scale(1.0)";
        }}
        disabled={loading}
        aria-busy={loading}
        aria-label="Upload files"
      >
        <Upload color="white" size={26} />
      </button>

      {/* Loading Modal */}
      {loading && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Uploading files"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10000,
          }}
        >
          <div
            style={{
              width: "min(92vw, 420px)",
              background: "white",
              borderRadius: 16,
              padding: 24,
              boxShadow: "0 10px 30px rgba(0,0,0,0.25)",
              textAlign: "center",
            }}
          >
            {/* Spinner */}
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "50%",
                margin: "0 auto 16px",
                border: "4px solid #e5e7eb",
                borderTopColor: "#2563eb",
                animation: "spin 1s linear infinite",
              }}
            />
            <h3 style={{ margin: "0 0 6px", fontSize: 18, fontWeight: 700 }}>
              Uploading…
            </h3>
            <p style={{ margin: 0, color: "#6b7280", fontSize: 14 }}>
              Please wait while we process your file(s).
            </p>
          </div>

          {/* keyframes */}
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      )}

      {/* Success Modal */}
      {successOpen && !loading && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Upload complete"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10000,
          }}
          onClick={() => setSuccessOpen(false)}
        >
          <div
            style={{
              width: "min(92vw, 520px)",
              background: "white",
              borderRadius: 16,
              padding: 20,
              boxShadow: "0 10px 30px rgba(0,0,0,0.25)",
              position: "relative",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setSuccessOpen(false)}
              aria-label="Close"
              style={{
                position: "absolute",
                top: 12,
                right: 12,
                background: "transparent",
                border: "none",
                cursor: "pointer",
              }}
            >
              <X size={20} />
            </button>

            <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 8 }}>
              <CheckCircle2 size={28} color="#16a34a" />
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Upload complete</h3>
            </div>

            <p style={{ margin: 0, color: "#374151", whiteSpace: "pre-wrap" }}>
              {successText}
            </p>
          </div>
        </div>
      )}
    </>
  );
}
