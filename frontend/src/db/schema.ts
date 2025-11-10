import { integer, pgTable, varchar, text, timestamp, jsonb, serial } from "drizzle-orm/pg-core";


export const tridAnalysisTable = pgTable("trid_analysis", {
  id: serial("id").primaryKey(),  
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
  loanEstimateFileName: varchar("loan_estimate_file_name", { length: 500 }),
  closingDisclosureFileName: varchar("closing_disclosure_file_name", { length: 500 }),
  loanId: varchar("loan_id", { length: 100 }),
  applicantName: varchar("applicant_name", { length: 500 }),
  propertyAddress: text("property_address"),
  salePrice: varchar("sale_price", { length: 50 }),
  loanAmount: varchar("loan_amount", { length: 50 }),
  loanEstimateData: jsonb("loan_estimate_data"),
  closingDisclosureData: jsonb("closing_disclosure_data"),
  tridComparison: jsonb("trid_comparison"),
  processingStatus: varchar("processing_status", { length: 50 }).default("pending").notNull(),
  errorMessage: text("error_message"),  
  backendPipeline: varchar("backend_pipeline", { length: 200 }),
  landingModel: varchar("landing_model", { length: 100 }),
  geminiModel: varchar("gemini_model", { length: 100 }),
});
