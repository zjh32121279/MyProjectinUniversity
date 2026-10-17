export type BookItem = {
  id: number;
  book_code?: string | null;
  title?: string | null;
  author?: string | null;
  publisher?: string | null;
  publish_year?: number | null;
  isbn?: string | null;
  language?: string | null;
  edition?: string | null;
  pages?: number | null;
  price_yuan?: number | null;
  clc_code?: string | null;
  call_number?: string | null;
  category_id?: number | null;
  category_code?: string | null;
  category_name?: string | null;
  subcategory_id?: number | null;
  subcategory_code?: string | null;
  subcategory_name?: string | null;
  keywords?: string | null;
  introduction?: string | null;
  total_copies?: number | null;
  available_copies?: number | null;
  borrowed_copies?: number | null;
  reserved_copies?: number | null;
  unavailable_copies?: number | null;
  circulation_type?: string | null;
  copy_stats?: Record<string, number>;
  primary_zone?: {
    zone_id?: number | null;
    zone_code?: string | null;
    zone_name?: string | null;
  } | null;
  sample_copies?: BookCopy[];
  cover_url?: string | null;
  cover_source?: string | null;
  cover_status?: string | null;
};

export type BookCopy = {
  id: number;
  copy_code?: string | null;
  barcode?: string | null;
  status?: string | null;
  copy_status?: string | null;
  status_name?: string | null;
  book_id?: number | null;
  book_code?: string | null;
  title?: string | null;
  circulation_type?: string | null;
  location?: {
    zone_id?: number | null;
    zone_code?: string | null;
    zone_name?: string | null;
    shelf_id?: number | null;
    shelf_code?: string | null;
    floor?: string | null;
    current_position_id?: number | null;
    position_code?: string | null;
    shelf_position?: string | null;
  } | null;
};

export type CategoryOption = {
  id?: number | null;
  code?: string | null;
  category_code?: string | null;
  name: string;
  book_count?: number | null;
};

export type ZoneOption = {
  id?: number | null;
  zone_id?: number | null;
  zone_code?: string | null;
  code?: string | null;
  zone_name?: string | null;
  name?: string | null;
  floor?: string | null;
  main_use?: string | null;
};

export type BookFilterOptions = {
  categories: CategoryOption[];
  zones: ZoneOption[];
  floors: string[];
  availability: string[];
};

export type BookSearchParams = {
  keyword?: string;
  category_id?: number;
  category_code?: string;
  availability?: string;
  circulation_type?: string;
  zone?: string;
  floor?: string;
  sort?: string;
  limit?: number;
  offset?: number;
};
