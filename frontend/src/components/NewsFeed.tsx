/**
 * News Feed Component
 * Displays news articles with sentiment analysis
 */
'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { newsService, getSentimentLabel, getSentimentColor, getSentimentGradient } from '@/services/news';
import { NewsArticle, SentimentLabel, NewsFilters } from '@/types/news';
import Card from './ui/Card';
import { ExternalLink, TrendingUp, TrendingDown, Minus, Clock, Filter, Newspaper } from 'lucide-react';
import CategoryIcon from './CategoryIcon';
import { getAssetCategory } from '@/types';
import Button from './ui/Button';
import EmptyState from './EmptyState';

interface NewsFeedProps {
  symbol?: string;
  limit?: number;
  showFilters?: boolean;
}

export default function NewsFeed({ symbol, limit = 5, showFilters = true }: NewsFeedProps) {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<NewsFilters>({
    categories: [],
    symbols: [],
    sentiment: [],
  });
  const [showFilterPanel, setShowFilterPanel] = useState(false);

  useEffect(() => {
    loadNews();
  }, [symbol, filters]);

  const loadNews = async () => {
    setIsLoading(true);
    try {
      const response = await newsService.getNews({
        ...filters,
        symbols: symbol ? [symbol] : filters.symbols,
      });
      setArticles(response.articles.slice(0, limit));
    } catch (error) {
      console.error('Failed to load news:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleSentimentFilter = (label: SentimentLabel) => {
    setFilters((prev) => {
      const current = prev.sentiment || [];
      const updated = current.includes(label)
        ? current.filter((s) => s !== label)
        : [...current, label];
      return { ...prev, sentiment: updated };
    });
  };

  const getRelativeTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const sentimentOptions: { label: SentimentLabel; color: string; icon: React.ReactNode }[] = [
    { label: 'very_bullish', color: '#10B981', icon: <TrendingUp className="w-3 h-3" /> },
    { label: 'bullish', color: '#34D399', icon: <TrendingUp className="w-3 h-3" /> },
    { label: 'neutral', color: '#9CA3AF', icon: <Minus className="w-3 h-3" /> },
    { label: 'bearish', color: '#F87171', icon: <TrendingDown className="w-3 h-3" /> },
    { label: 'very_bearish', color: '#EF4444', icon: <TrendingDown className="w-3 h-3" /> },
  ];

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i} className="p-4">
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4" />
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-full" />
            </div>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div>
      {/* Header with Filter Toggle */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Clock className="w-5 h-5 text-purple-600" />
          Latest News
        </h3>
        {showFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowFilterPanel(!showFilterPanel)}
            leftIcon={<Filter className="w-4 h-4" />}
          >
            Filters
          </Button>
        )}
      </div>

      {/* Sentiment Filter Panel */}
      <AnimatePresence>
        {showFilterPanel && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mb-4 overflow-hidden"
          >
            <Card variant="outlined" padding="sm" className="mb-4">
              <div className="flex flex-wrap gap-2">
                <span className="text-sm text-gray-600 dark:text-gray-400 mr-2">Sentiment:</span>
                {sentimentOptions.map((option) => {
                  const isActive = filters.sentiment?.includes(option.label);
                  return (
                    <button
                      key={option.label}
                      onClick={() => toggleSentimentFilter(option.label)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${isActive
                          ? 'text-white shadow-md'
                          : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300'
                        }`}
                      style={{
                        backgroundColor: isActive ? option.color : undefined,
                      }}
                    >
                      {option.icon}
                      {option.label.replace('_', ' ')}
                    </button>
                  );
                })}
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* News Articles */}
      <div className="space-y-4">
        {articles.length === 0 ? (
          <EmptyState
            icon={<Newspaper className="w-12 h-12 text-gray-300 dark:text-gray-600" />}
            title="No news articles"
            description="Check back later for the latest crypto news and updates"
            size="sm"
          />
        ) : (
          articles.map((article, index) => {
            const sentimentLabel = article.sentimentLabel || getSentimentLabel(article.sentiment || 0);
            const sentimentColor = getSentimentColor(article.sentiment || 0);
            const sentimentOption = sentimentOptions.find((o) => o.label === sentimentLabel);

            return (
              <motion.div
                key={article.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <Card hover className="p-4 group cursor-pointer" variant="elevated">
                  <div className="flex gap-4">
                    {/* Image */}
                    {article.imageUrl && (
                      <div className="flex-shrink-0 w-20 h-20 rounded-lg overflow-hidden">
                        <img
                          src={article.imageUrl}
                          alt={article.title}
                          className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                        />
                      </div>
                    )}

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      {/* Header */}
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex-1">
                          <h4 className="text-sm font-semibold text-gray-900 dark:text-white line-clamp-2 group-hover:text-purple-600 transition-colors">
                            {article.title}
                          </h4>
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            {article.source} • {getRelativeTime(article.publishedAt)}
                          </p>
                        </div>

                        {/* Sentiment Badge */}
                        {sentimentOption && (
                          <div
                            className="flex-shrink-0 px-2.5 py-1 rounded-full text-xs font-medium text-white flex items-center gap-1"
                            style={{ backgroundColor: sentimentColor }}
                          >
                            {sentimentOption.icon}
                            {sentimentOption.label.replace('_', ' ')}
                          </div>
                        )}
                      </div>

                      {/* Summary */}
                      <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mb-3">
                        {article.summary}
                      </p>

                      {/* Tags */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Symbol Tags */}
                        {article.symbols.slice(0, 3).map((symbol) => {
                          const category = getAssetCategory(symbol);
                          return (
                            <div key={symbol} className="flex items-center gap-1">
                              <CategoryIcon category={category} size="sm" />
                              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                                {symbol}
                              </span>
                            </div>
                          );
                        })}

                        {/* External Link */}
                        <a
                          href={article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1 ml-auto"
                        >
                          Read More
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    </div>
                  </div>
                </Card>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
}
