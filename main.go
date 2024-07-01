package main

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"mime/multipart"
	"net/http"
	"os"

	_ "github.com/mattn/go-sqlite3"
	_ "github.com/primalmotion/simplai/vectorstore/chromadb"
	"golang.org/x/crypto/bcrypt"
)

var db *sql.DB
var shortdb *sql.DB

type User struct {
	username string
	email    string
	hash     []byte
	role     string
}

type NER struct {
	Name      string `json:"name"`
	Email     string `json:"email"`
	WorkTitle []struct {
		Position     string `json:"position"`
		Organisation string `json:"organisation"`
	} `json:"work_title"`
	WorkLocation []string `json:"work_location"`
	TechSkills   []string `json:"tech_skills"`
	SoftSkills   []string `json:"soft_skills"`
	Summary      string   `json:"summary"`
}

var U = User{"", "", nil, ""}

type QueryRequest struct {
	Query string `json:"query"`
}

type QueryResponse []struct {
	ChromaID string `json:"chroma_id"`
	Info     string `json:"info"`
}

type JobApplication struct {
	UserID         string `json:"userid"`
	JobDescription string `json:"jobdescription"`
	ShortlistedBy  string `json:"shortlisted_by"`
}

func main() {
	var err error
	db, err = sql.Open("sqlite3", "./db/users.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS users (
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						username TEXT UNIQUE NOT NULL,
						email TEXT UNIQUE NOT NULL,
						password TEXT NOT NULL,
						role TEXT DEFAULT 'candidate' NOT NULL
					)`)
	if err != nil {
		log.Fatal("Error creating users table:", err)
	}

	// Check if the database connection is alive
	err = db.Ping()
	if err != nil {
		log.Fatal("Error connecting to the database:", err)
	}
	fmt.Println("Connected to the database successfully!")

	mux := http.NewServeMux()

	mux.Handle("/", http.FileServer(http.Dir("templates")))
	mux.Handle("/assets/*", http.FileServer(http.Dir("templates/assets")))
	mux.Handle("/about_us.html", http.FileServer(http.Dir("templates")))
	mux.Handle("/contact_us.html", http.FileServer(http.Dir("templates")))
	mux.Handle("/testimonial.html", http.FileServer(http.Dir("templates")))
	mux.Handle("/signup.html", http.FileServer(http.Dir("templates")))
	mux.Handle("/uploadresume.html", http.FileServer(http.Dir("templates")))
	mux.Handle("/login.html", http.FileServer(http.Dir("templates")))
	mux.Handle("/client_login.html", http.FileServer(http.Dir("templates")))
	mux.Handle("/admin_login.html", http.FileServer(http.Dir("templates")))
	mux.Handle("/candidate_login.html", http.FileServer(http.Dir("templates")))

	mux.HandleFunc("/signup", signupHandler)
	mux.HandleFunc("/uploadresume", uploadHandler)
	mux.HandleFunc("/receive-ner", receiveNERHandler)
	mux.HandleFunc("/submit-query", queryHandler)
	mux.HandleFunc("/job_applications", jobApplicationsHandler)
	mux.HandleFunc("/shortlist", shortlistHandler)
	mux.HandleFunc("/login", loginHandler)

	fmt.Println("Server is running at http://localhost:8080")
	http.ListenAndServe(":8080", mux)
}

func uploadHandler(w http.ResponseWriter, r *http.Request) {
	var err error
	db, err = sql.Open("sqlite3", "./db/users.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	// Parse the multipart form in the request
	err = r.ParseMultipartForm(10 << 20) // 10 MB is the max file size
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Get the file from the form
	file, handler, err := r.FormFile("file")
	if err != nil {
		http.Error(w, "Failed to get file from form", http.StatusBadRequest)
		fmt.Println(err)
		return
	}
	defer file.Close()

	// create a new buffer to hold the multipart data
	var b bytes.Buffer
	writer := multipart.NewWriter(&b)

	// Create a form field for the file
	part, err := writer.CreateFormFile("file", handler.Filename)
	if err != nil {
		http.Error(w, "Error creating form file", http.StatusInternalServerError)
		return
	}

	// Copy the file content to the form field
	if _, err := io.Copy(part, file); err != nil {
		http.Error(w, "Error copying file content", http.StatusInternalServerError)
		return
	}

	// Close the writer to finalize the form data
	if err := writer.Close(); err != nil {
		http.Error(w, "Error finalizing form data", http.StatusInternalServerError)
		return
	}

	// Send the multipart form data to the Flask server
	resp, err := http.Post("http://localhost:5050/uploadresume_toNER", writer.FormDataContentType(), &b)
	if err != nil {
		http.Error(w, "Error sending file to Flask server", http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		http.Error(w, "Unexpected response from server", http.StatusInternalServerError)
		return
	}

	_, err = db.Exec("INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)", U.username, U.email, U.hash, U.role)
	if err != nil {
		log.Println("Error inserting user:", err)
		http.Error(w, "Error inserting user", http.StatusInternalServerError)
		return
	}
	http.Redirect(w, r, "/login.html", http.StatusSeeOther)
	fmt.Printf("User %s signed up successfully!\n", U.username)
}

func signupHandler(w http.ResponseWriter, r *http.Request) {
	var err error
	db, err = sql.Open("sqlite3", "./db/users.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	r.ParseForm()
	hash, e := bcrypt.GenerateFromPassword([]byte(r.FormValue("password")), bcrypt.DefaultCost)
	if e != nil {
		fmt.Println("Error hashing password:", e)
		panic(e)
	}
	U = User{r.FormValue("username"), r.FormValue("email"), hash, r.FormValue("roles")}
	switch U.role {
	case "Candidate":
		resp, err := http.Post("http://localhost:5050/sendusername", "text/plain", bytes.NewBuffer([]byte(U.username)))
		if err != nil {
			http.Error(w, "Error sending data to Flask server", http.StatusInternalServerError)
			return
		}
		defer resp.Body.Close()
		http.Redirect(w, r, "/uploadresume.html", http.StatusSeeOther) // Serve candidate signup page
	case "Client":
		_, err := db.Exec("INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)", U.username, U.email, U.hash, U.role)
		if err != nil {
			log.Println("Error inserting user:", err)
			http.Error(w, "Error inserting user", http.StatusInternalServerError)
			return
		}
		http.Redirect(w, r, "/login.html", http.StatusSeeOther)
		fmt.Printf("User %s signed up successfully!\n", U.username)
	case "Admin":
		_, err := db.Exec("INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)", U.username, U.email, U.hash, U.role)
		if err != nil {
			log.Println("Error inserting user:", err)
			http.Error(w, "Error inserting user", http.StatusInternalServerError)
			return
		}
		http.Redirect(w, r, "/login.html", http.StatusSeeOther)
		fmt.Printf("User %s signed up successfully!\n", U.username)
	default:
		http.Error(w, "Invalid role", http.StatusBadRequest)
	}
}

func receiveNERHandler(w http.ResponseWriter, r *http.Request) {
	fmt.Println("Handling the json now!")

	var n NER
	jsonFile, err := os.Open("./servers/ner/tmp/ner.json")
	if err != nil {
		log.Fatalf("Failed to open JSON file: %v", err)
	}
	defer jsonFile.Close()

	byteValue, err := io.ReadAll(jsonFile)
	if err != nil {
		log.Fatalf("Failed to read JSON file: %v", err)
	}

	if err := json.Unmarshal(byteValue, &n); err != nil {
		log.Fatalf("Failed to unmarshal JSON content: %v", err)
	}

	prettyPrintStruct(n) // this line is just for logging purposes can be commented out

	fmt.Println("The name of the user is:", U.username)

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("Data received successfully"))
}

// this function is written for documentation purposes
// can be commented out
func prettyPrintStruct(v interface{}) {
	prettyJSON, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		log.Fatalf("Failed to generate pretty JSON: %v", err)
	}
	fmt.Println(string(prettyJSON))
}

func queryHandler(w http.ResponseWriter, r *http.Request) {
	var queryRequest QueryRequest
	err := json.NewDecoder(r.Body).Decode(&queryRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	forwardUrl := "http://localhost:5050/ner-query"
	forwardResponse, err := forwardQuery(forwardUrl, queryRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	// prettyPrintStruct(forwardResponse)
	forwardResponseSlice := *forwardResponse

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(forwardResponseSlice)
}

func forwardQuery(url string, queryRequest QueryRequest) (*QueryResponse, error) {
	jsonData, err := json.Marshal(queryRequest)
	if err != nil {
		return nil, err
	}

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var queryResponse QueryResponse
	err = json.Unmarshal(body, &queryResponse)
	if err != nil {
		return nil, err
	}
	// fmt.Println(queryResponse)

	return &queryResponse, nil
}

func jobApplicationsHandler(w http.ResponseWriter, r *http.Request) {
	var err error
	shortdb, err = sql.Open("sqlite3", "./db/shortlisted.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	rows, err := shortdb.Query("SELECT userid, jobdescription, shortlistedby FROM job_applications")
	if err != nil {
		log.Fatal(err)
	}
	defer rows.Close()

	var applications []JobApplication
	for rows.Next() {
		var app JobApplication
		err = rows.Scan(&app.UserID, &app.JobDescription, &app.ShortlistedBy)
		if err != nil {
			log.Fatal(err)
		}
		fmt.Println(app)
		applications = append(applications, app)
	}
	fmt.Println(applications)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(applications)
}

func shortlistHandler(w http.ResponseWriter, r *http.Request) {
	err := r.ParseForm()
	if err != nil {
		fmt.Fprintf(w, "Error parsing form data: %v", err)
		return
	}

	u := r.Form.Get("user_id")
	j := r.Form.Get("job_description")
	// fmt.Println(u, j)

	shortdb, err = sql.Open("sqlite3", "./db/shortlisted.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	_, err = shortdb.Exec("INSERT INTO job_applications (userid, jobdescription, shortlistedby) VALUES (?, ?, ?)", u, j, "client")
	if err != nil {
		fmt.Println("Error shortlisting candidate...")
	}
	fmt.Println("Shortlist data received!")
	http.Redirect(w, r, "/client_login.html", http.StatusSeeOther)

}

func loginHandler(w http.ResponseWriter, r *http.Request) {
	err := r.ParseForm()
	if err != nil {
		fmt.Fprintf(w, "Error parsing form data: %v", err)
		return
	}

	u := r.Form.Get("username")
	p := r.Form.Get("password")
	fmt.Println(u, p)
	fmt.Println("Login data recieved!")
	// http.Redirect(w, r, "/login.html", http.StatusSeeOther)

	// hash, err := bcrypt.GenerateFromPassword([]byte(p), bcrypt.DefaultCost)
	// if err != nil {
	// 	log.Fatal(err)
	// }

	db, err := sql.Open("sqlite3", "./db/users.db")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	var storedHash string
	query := "SELECT password FROM users WHERE username = ?"
	err = db.QueryRow(query, u).Scan(&storedHash)
	if err != nil {
		fmt.Println("User not present")
		http.Redirect(w, r, "/login.html", http.StatusSeeOther)
	}
	// fmt.Println(storedHash)

	err = bcrypt.CompareHashAndPassword([]byte(storedHash), []byte(p))
	if err != nil {
		fmt.Println("Password incorrect!")
		http.Redirect(w, r, "/login.html", http.StatusSeeOther)
	}
	fmt.Println("Password is correct!")

	var role string
	query = "SELECT role FROM users WHERE username = ?"
	err = db.QueryRow(query, u).Scan(&role)
	if err != nil {
		fmt.Println(err)
	}
	// fmt.Println(role)

	switch role {
	case "Candidate":
		http.Redirect(w, r, "/candidate_login.html", http.StatusSeeOther)
	case "Admin":
		http.Redirect(w, r, "/admin_login.html", http.StatusSeeOther)
	case "Client":
		http.Redirect(w, r, "/client_login.html", http.StatusSeeOther)
	default:
		fmt.Println("Something went wrong, redirecting to login page...")
		http.Redirect(w, r, "/login.html", http.StatusSeeOther)
	}

}
