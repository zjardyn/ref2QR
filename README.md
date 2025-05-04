# Reference to QR Code Converter

A Flask application that converts academic reference files (BibTeX, RDF, RIS, EndNote XML) into QR codes linking to formatted reference lists. It also supports creating QR codes for Google Documents.

## Features

- Convert reference files (.bib, .rdf, .ris, .xml) to QR codes
- Link directly to Google Docs with QR codes
- Persistent storage of reference data as html files
- Automatic expiration of old references 
   -TODO: change the experiation to longer than 30 days
- Admin tools for database monitoring and maintenance

## Google Docs Integration

First, the application supports creating QR codes that link directly to Google Documents:

1. Choose "Option 1: Link to Google Document" on the main page
1. Paste the Google Docs URL
3. Generate a QR code that will redirect users directly to your document

## Database Features

The dev application uses SQLAlchemy to store references in a persistent database instead of in-memory storage. This means:

- Reference lists persist across server restarts
- References can have expiration dates (default: 30 days)
- Automatic cleanup of expired references

### Database Setup

By default, the application uses SQLite for development, which requires no additional setup:

```
# SQLite database will be created automatically at:
references.db
```

For production, you can configure PostgreSQL by setting the `DATABASE_URL` environment variable:

```bash
# Example PostgreSQL connection
export DATABASE_URL=postgresql://username:password@localhost/references
```

Then modify `database.py` to use this environment variable.

### Database Maintenance and Monitoring

The application includes administrative endpoints to help manage the database:

#### Cleanup Endpoint

Expired references can be cleaned up automatically using the cleanup endpoint:

```
http://localhost:5000/maintenance/cleanup?key=change_this_key_for_production
```

Set up a cron job or scheduled task to call this endpoint regularly (e.g., daily):

```bash
# Example cron job (daily at 2 AM)
0 2 * * * curl https://your-domain.com/maintenance/cleanup?key=your_maintenance_key
```

#### Delete All References 

If you need to completely reset the database and remove all reference lists:

```
http://localhost:5000/admin/delete-all?key=change_this_key_for_production
```

**Warning**: This will permanently delete all references from the database. A confirmation page will be shown before deletion.

#### Database Statistics

You can view statistics about the database contents at this direct URL:

```
http://localhost:5000/admin/stats?key=change_this_key_for_production
```

This shows:
- Total number of reference lists
- Number of active vs. expired reference lists
- Details about the most recently created reference lists
- Links to view the references
- Option to clean up expired references

The maintenance key is set in `app.py` and should be changed to a secure value in production.



Th app has limit

## Test Capabilities

Automated tests are provided to verify the core functionality of the application:

- **File Upload Tests**: The test suite uploads example reference files (`.bib`, `.rdf`, `.ris`, `.xml`) from the `old/` directory and checks that the application processes them correctly and generates a QR code for each.
- **Google Docs URL Test**: The test suite submits a Google Docs URL and verifies that a QR code is generated for the link.

Tests are located in `tests/test_uploads.py` and use `pytest` as the test runner.

### Running the Tests

1. Ensure you have the required dependencies installed (see below).
2. Run the tests from the project root with:
   ```bash
   pytest
   ```

# TODO:

1. The `Upload & Generate QR` button should check for email and sms verification.
2. We want to store the user info in the database, and also what type of file was uploaded (.bib, .rdf, .xml, or .ris)


## Installation and Setup

1. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Access the application at http://localhost:5000 