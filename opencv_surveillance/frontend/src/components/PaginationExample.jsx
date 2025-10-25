// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Pagination Component Usage Example
 *
 * This example demonstrates how to use the Pagination component
 * with API endpoints that support page-based pagination.
 */

import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';
import Pagination from './Pagination';

function PaginatedDataExample() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Fetch data whenever page or page size changes
  useEffect(() => {
    fetchData();
  }, [currentPage, pageSize]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Make API request with pagination parameters
      const response = await apiClient.get('/recordings/', {
        params: {
          page: currentPage,
          page_size: pageSize,
        },
      });

      // Update state from response
      setData(response.data.recordings || []);
      setTotalItems(response.data.total || 0);
      setTotalPages(Math.ceil((response.data.total || 0) / pageSize));

    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (newPage) => {
    setCurrentPage(newPage);
    // Optionally scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handlePageSizeChange = (newPageSize) => {
    setPageSize(newPageSize);
    // Reset to first page when changing page size
    setCurrentPage(1);
  };

  return (
    <div className="paginated-data-container">
      <h2>Recordings</h2>

      {/* Error message */}
      {error && (
        <div className="error-message">{error}</div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="loading-message">Loading...</div>
      )}

      {/* Data display */}
      {!loading && data.length > 0 && (
        <div className="data-list">
          {data.map(item => (
            <div key={item.id} className="data-item">
              {/* Your data rendering here */}
              <p>{item.camera_id} - {new Date(item.started_at).toLocaleString()}</p>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && data.length === 0 && !error && (
        <div className="empty-message">No recordings found</div>
      )}

      {/* Pagination controls */}
      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        totalItems={totalItems}
        pageSize={pageSize}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
        pageSizeOptions={[20, 50, 100, 200]}
        showPageSize={true}
      />
    </div>
  );
}

export default PaginatedDataExample;


// ============================================================================
// ALTERNATIVE: Hook-based approach
// ============================================================================

/**
 * Custom hook for pagination
 *
 * Manages pagination state and provides helper functions
 */
export function usePagination(initialPageSize = 50) {
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [totalItems, setTotalItems] = useState(0);

  const totalPages = Math.ceil(totalItems / pageSize);

  const handlePageChange = (newPage) => {
    setCurrentPage(newPage);
  };

  const handlePageSizeChange = (newPageSize) => {
    setPageSize(newPageSize);
    setCurrentPage(1); // Reset to first page
  };

  const reset = () => {
    setCurrentPage(1);
    setTotalItems(0);
  };

  return {
    currentPage,
    pageSize,
    totalItems,
    totalPages,
    setTotalItems,
    handlePageChange,
    handlePageSizeChange,
    reset,
  };
}

// Example using the hook:
function PaginatedDataWithHook() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  const pagination = usePagination(50);

  useEffect(() => {
    fetchData();
  }, [pagination.currentPage, pagination.pageSize]);

  const fetchData = async () => {
    setLoading(true);
    const response = await apiClient.get('/recordings/', {
      params: {
        page: pagination.currentPage,
        page_size: pagination.pageSize,
      },
    });

    setData(response.data.recordings || []);
    pagination.setTotalItems(response.data.total || 0);
    setLoading(false);
  };

  return (
    <div>
      {/* Data rendering */}
      {data.map(item => (
        <div key={item.id}>{item.camera_id}</div>
      ))}

      {/* Pagination */}
      <Pagination
        currentPage={pagination.currentPage}
        totalPages={pagination.totalPages}
        totalItems={pagination.totalItems}
        pageSize={pagination.pageSize}
        onPageChange={pagination.handlePageChange}
        onPageSizeChange={pagination.handlePageSizeChange}
      />
    </div>
  );
}


// ============================================================================
// URL-based pagination (with React Router)
// ============================================================================

import { useSearchParams } from 'react-router-dom';

function PaginatedDataWithURL() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState([]);

  // Get pagination from URL or use defaults
  const currentPage = parseInt(searchParams.get('page') || '1', 10);
  const pageSize = parseInt(searchParams.get('page_size') || '50', 10);

  const [totalItems, setTotalItems] = useState(0);
  const totalPages = Math.ceil(totalItems / pageSize);

  useEffect(() => {
    fetchData();
  }, [currentPage, pageSize]);

  const fetchData = async () => {
    const response = await apiClient.get('/recordings/', {
      params: { page: currentPage, page_size: pageSize },
    });

    setData(response.data.recordings || []);
    setTotalItems(response.data.total || 0);
  };

  const handlePageChange = (newPage) => {
    setSearchParams({
      page: newPage.toString(),
      page_size: pageSize.toString(),
    });
  };

  const handlePageSizeChange = (newPageSize) => {
    setSearchParams({
      page: '1', // Reset to first page
      page_size: newPageSize.toString(),
    });
  };

  return (
    <div>
      {data.map(item => (
        <div key={item.id}>{item.camera_id}</div>
      ))}

      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        totalItems={totalItems}
        pageSize={pageSize}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />
    </div>
  );
}
