import React, { useState, useEffect } from 'react';
import { getApiUrl } from './api';
import { SenseLoader } from './Loader';

export default function ReportLibrary() {
  const [reports, setReports] = useState([]);
  const [typeFilter, setTypeFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  const [previewContent, setPreviewContent] = useState(null);
  const [previewFilename, setPreviewFilename] = useState('');
  const [showModal, setShowModal] = useState(false);

  const [loading, setLoading] = useState(true);

  const fetchReports = () => {
    setLoading(true);
    fetch(getApiUrl(`/api/reports?report_type=${typeFilter}&search=${searchTerm}`))
      .then((res) => res.json())
      .then((data) => setReports(data))
      .catch((err) => console.error('Error loading report library', err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchReports();
  }, [typeFilter, searchTerm]);

  const handlePreview = (filename) => {
    fetch(getApiUrl(`/api/reports/content/${filename}`))
      .then(res => res.json())
      .then(data => {
        setPreviewContent(data.content);
        setPreviewFilename(filename);
        setShowModal(true);
      })
      .catch(err => console.error("Error loading report content", err));
  };

  const handleDelete = (filename) => {
    if (!window.confirm(`Are you sure you want to delete ${filename}?`)) return;
    
    fetch(getApiUrl(`/api/reports/${filename}`), { method: 'DELETE' })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          fetchReports();
        } else {
          alert(`Delete failed: ${data.error}`);
        }
      })
      .catch(err => console.error("Error deleting report", err));
  };

  const handleDownloadMd = (filename) => {
    fetch(getApiUrl(`/api/reports/content/${filename}`))
      .then(res => res.json())
      .then(data => {
        const blob = new Blob([data.content], { type: 'text/markdown' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
      })
      .catch(err => console.error("Error downloading markdown", err));
  };

  return (
    <div className="report-section">
      <div className="action-panel">
        <div className="control-group" style={{ flexGrow: 1 }}>
          <label className="control-label">Filter by Type</label>
          <select 
            className="form-select" 
            value={typeFilter} 
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option>All</option>
            <option>Sector Reports</option>
            <option>Stock Analysis</option>
            <option>Top Picks</option>
            <option>Other</option>
          </select>
        </div>
        
        <div className="control-group" style={{ flexGrow: 2 }}>
          <label className="control-label">Search Reports</label>
          <input 
            type="text" 
            className="form-input" 
            placeholder="Enter ticker or keyword..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {loading && <SenseLoader label="Loading archive…" />}

      <div style={{ fontSize: "0.78rem", color: "var(--ink-muted)", marginBottom: "12px" }}>
        Showing {reports.length} archived items
      </div>

      {!loading && reports.length === 0 ? (
        <div style={{ padding: "40px", backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--r-lg)", textAlign: "center", color: "var(--ink-muted)" }}>
          No archived memos found matching filters.
        </div>
      ) : (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Report File</th>
                <th>Type</th>
                <th>Size (KB)</th>
                <th>Created At</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((rep, idx) => (
                <tr key={idx}>
                  <td style={{ fontWeight: "600", color: "var(--ink)" }}>{rep.filename}</td>
                  <td>
                    <span style={{
                      fontSize: "0.68rem",
                      fontWeight: "700",
                      padding: "2px 8px",
                      borderRadius: "var(--r-pill)",
                      backgroundColor: rep.type_label === 'Sector' ? "var(--green-subtle)" : rep.type_label === 'Stock Memo' ? "var(--brand-subtle)" : "var(--bg-surface)",
                      color: rep.type_label === 'Sector' ? "var(--green)" : rep.type_label === 'Stock Memo' ? "var(--brand)" : "var(--ink-secondary)",
                      border: "1px solid transparent"
                    }}>
                      {rep.type_label}
                    </span>
                  </td>
                  <td style={{ fontFamily: "monospace" }}>{rep.size_kb} KB</td>
                  <td>{rep.mod_time}</td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "inline-flex", gap: "6px" }}>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: "0.72rem" }} onClick={() => handlePreview(rep.filename)}>
                        Preview
                      </button>
                      <button className="btn btn-primary" style={{ padding: "4px 8px", fontSize: "0.72rem" }} onClick={() => window.open(getApiUrl(`/api/reports/pdf/${rep.filename}`), '_blank')}>
                        PDF
                      </button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: "0.72rem" }} onClick={() => handleDownloadMd(rep.filename)}>
                        MD
                      </button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: "0.72rem", color: "var(--red)", borderColor: "var(--red-border)" }} onClick={() => handleDelete(rep.filename)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontWeight: "800", fontSize: "1.1rem" }}>{previewFilename}</h3>
              <button className="icon-btn" onClick={() => setShowModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="markdown-body">
                <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "0.85rem", color: "var(--ink-secondary)" }}>
                  {previewContent}
                </pre>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setShowModal(false)}>Close</button>
              <button className="btn" onClick={() => handleDownloadMd(previewFilename)}>Download Markdown</button>
              <button className="btn btn-primary" onClick={() => window.open(getApiUrl(`/api/reports/pdf/${previewFilename}`), '_blank')}>
                Download PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
