// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Pagination Component
 *
 * Reusable pagination component for navigating through paginated data.
 * Supports page-based navigation with customizable page size.
 *
 * @param {Object} props - Component props
 * @param {number} props.currentPage - Current page number (1-indexed)
 * @param {number} props.totalPages - Total number of pages
 * @param {number} props.totalItems - Total number of items
 * @param {number} props.pageSize - Number of items per page
 * @param {Function} props.onPageChange - Callback when page changes
 * @param {Function} props.onPageSizeChange - Callback when page size changes
 * @param {Array<number>} props.pageSizeOptions - Available page size options
 * @param {boolean} props.showPageSize - Whether to show page size selector
 */

import React from 'react';
import './Pagination.css';

function Pagination({
  currentPage = 1,
  totalPages = 1,
  totalItems = 0,
  pageSize = 50,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [20, 50, 100, 200],
  showPageSize = true,
}) {
  // Calculate range of items shown
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  // Handle page navigation
  const goToPage = (page) => {
    if (page >= 1 && page <= totalPages && page !== currentPage) {
      onPageChange(page);
    }
  };

  const goToFirstPage = () => goToPage(1);
  const goToPrevPage = () => goToPage(currentPage - 1);
  const goToNextPage = () => goToPage(currentPage + 1);
  const goToLastPage = () => goToPage(totalPages);

  // Handle page size change
  const handlePageSizeChange = (e) => {
    const newPageSize = parseInt(e.target.value);
    if (onPageSizeChange) {
      onPageSizeChange(newPageSize);
    }
  };

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages = [];
    const maxPagesToShow = 7;

    if (totalPages <= maxPagesToShow) {
      // Show all pages
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Show first, last, and pages around current
      pages.push(1);

      let startPage = Math.max(2, currentPage - 2);
      let endPage = Math.min(totalPages - 1, currentPage + 2);

      // Add ellipsis before
      if (startPage > 2) {
        pages.push('...');
      }

      // Add middle pages
      for (let i = startPage; i <= endPage; i++) {
        pages.push(i);
      }

      // Add ellipsis after
      if (endPage < totalPages - 1) {
        pages.push('...');
      }

      pages.push(totalPages);
    }

    return pages;
  };

  // Don't render if no items
  if (totalItems === 0) {
    return (
      <div className="pagination">
        <div className="pagination-info">
          No items to display
        </div>
      </div>
    );
  }

  return (
    <div className="pagination">
      {/* Items info */}
      <div className="pagination-info">
        Showing {startItem}-{endItem} of {totalItems.toLocaleString()} items
      </div>

      {/* Page size selector */}
      {showPageSize && onPageSizeChange && (
        <div className="pagination-page-size">
          <label htmlFor="page-size-select">Items per page:</label>
          <select
            id="page-size-select"
            value={pageSize}
            onChange={handlePageSizeChange}
            className="page-size-select"
          >
            {pageSizeOptions.map(size => (
              <key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Page navigation */}
      <div className="pagination-controls">
        {/* First page button */}
        <button
          className="pagination-btn"
          onClick={goToFirstPage}
          disabled={currentPage === 1}
          aria-label="First page"
          title="First page"
        >
          «
        </button>

        {/* Previous page button */}
        <button
          className="pagination-btn"
          onClick={goToPrevPage}
          disabled={currentPage === 1}
          aria-label="Previous page"
          title="Previous page"
        >
          ‹
        </button>

        {/* Page numbers */}
        <div className="pagination-pages">
          {getPageNumbers().map((page, index) => {
            if (page === '...') {
              return (
                <span key={`ellipsis-${index}`} className="pagination-ellipsis">
                  …
                </span>
              );
            }

            return (
              <button
                key={page}
                className={`pagination-btn ${page === currentPage ? 'active' : ''}`}
                onClick={() => goToPage(page)}
                aria-label={`Page ${page}`}
                aria-current={page === currentPage ? 'page' : undefined}
              >
                {page}
              </button>
            );
          })}
        </div>

        {/* Next page button */}
        <button
          className="pagination-btn"
          onClick={goToNextPage}
          disabled={currentPage === totalPages}
          aria-label="Next page"
          title="Next page"
        >
          ›
        </button>

        {/* Last page button */}
        <button
          className="pagination-btn"
          onClick={goToLastPage}
          disabled={currentPage === totalPages}
          aria-label="Last page"
          title="Last page"
        >
          »
        </button>
      </div>

      {/* Page info */}
      <div className="pagination-page-info">
        Page {currentPage} of {totalPages}
      </div>
    </div>
  );
}

export default Pagination;
