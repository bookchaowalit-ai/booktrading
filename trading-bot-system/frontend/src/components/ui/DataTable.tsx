/**
 * Compact DataTable Component
 * Shopify-style data table
 */
interface Column<T> {
  key: keyof T | string;
  header: string;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
  size?: 'sm' | 'md';
}

export default function DataTable<T extends Record<string, any>>({
  data,
  columns,
  emptyMessage = 'No data available',
  onRowClick,
  size = 'sm',
}: DataTableProps<T>) {
  const getValue = (item: T, key: string) => {
    const keys = key.split('.');
    return keys.reduce((obj, k) => obj?.[k], item as any);
  };

  if (data.length === 0) {
    return (
      <div className={`text-center py-8 ${size === 'sm' ? 'py-6' : 'py-8'}`}>
        <p className="text-sm text-gray-500 dark:text-gray-400">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className={`border-b border-gray-200 dark:border-gray-700 ${size === 'sm' ? 'text-xs' : 'text-sm'}`}>
            {columns.map((column) => (
              <th
                key={String(column.key)}
                className={`text-left font-medium text-gray-600 dark:text-gray-400 ${column.className || ''} ${size === 'sm' ? 'px-3 py-2' : 'px-4 py-3'}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((item, index) => (
            <tr
              key={index}
              onClick={() => onRowClick?.(item)}
              className={`
                border-b border-gray-100 dark:border-gray-800
                ${onRowClick ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50' : ''}
                ${size === 'sm' ? 'text-xs' : 'text-sm'}
              `}
            >
              {columns.map((column) => (
                <td
                  key={String(column.key)}
                  className={`${column.className || ''} ${size === 'sm' ? 'px-3 py-2.5' : 'px-4 py-3'}`}
                >
                  {column.render
                    ? column.render(item)
                    : getValue(item, String(column.key))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
