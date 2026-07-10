use serde::{Deserialize, Serialize};
use std::env;
use std::fs::File;
use std::io::{BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};
use jwalk::WalkDirGeneric;

#[derive(Debug, Serialize, Deserialize)]
struct Config {
    scan_targets: Vec<String>,
    ignore_exact_folders: Vec<String>,
    ignore_folder_names: Vec<String>,
    #[serde(default)]
    media_source_paths: Vec<String>,
}

fn load_config() -> Result<Config, Box<dyn std::error::Error>> {
    // Attempt to load config.json (or config.json.bak as fallback during transition)
    let mut config_path = PathBuf::from("config.json");
    if !config_path.exists() {
        if let Ok(exe_path) = env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                config_path = exe_dir.join("config.json");
                if !config_path.exists() {
                    config_path = exe_dir.join("config.json.bak");
                }
            }
        }
    } else {
        // Current directory check
        if !config_path.exists() {
            config_path = PathBuf::from("config.json.bak");
        }
    }

    let file = File::open(&config_path)?;
    let reader = BufReader::new(file);
    let config: Config = serde_json::from_reader(reader)?;
    Ok(config)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    let is_media = args.contains(&"--media".to_string());

    if is_media {
        println!("Status: Initializing media scanner...");
    } else {
        println!("Status: Initializing standard scanner...");
    }
    
    let config = match load_config() {
        Ok(cfg) => cfg,
        Err(e) => {
            eprintln!("Error: Failed to load config.json: {}", e);
            std::process::exit(1);
        }
    };

    let target_paths = if is_media {
        &config.media_source_paths
    } else {
        &config.scan_targets
    };

    // Canonicalize scan roots and ignore paths
    let scan_paths: Vec<PathBuf> = target_paths.iter()
        .map(|p| Path::new(p).canonicalize().unwrap_or_else(|_| PathBuf::from(p)))
        .collect();

    let ignored_path_strings: Vec<String> = config.ignore_exact_folders.iter()
        .map(|p| {
            let canonical = Path::new(p).canonicalize().unwrap_or_else(|_| PathBuf::from(p));
            canonical.to_string_lossy().to_lowercase()
        })
        .collect();

    let ignore_folder_names: Vec<String> = config.ignore_folder_names.iter()
        .map(|s| s.to_lowercase())
        .collect();

    // Prepare output filename
    let out_filename = if is_media {
        "media_index.txt"
    } else {
        "hard_drive_index.txt"
    };

    let mut output_path = PathBuf::from(out_filename);
    if let Ok(exe_path) = env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            output_path = exe_dir.join(out_filename);
        }
    }

    let file = File::create(&output_path)?;
    let mut writer = BufWriter::new(file);
    let mut file_count = 0;

    println!("Status: Commencing file walk...");

    for root in scan_paths {
        println!("Status: Scanning folder: {}", root.display());
        
        let ignored_path_strings_clone = ignored_path_strings.clone();
        let ignore_folder_names_clone = ignore_folder_names.clone();

        let walk_dir = WalkDirGeneric::<((), ())>::new(&root)
            .process_read_dir(move |_depth, _path, _state, children| {
                children.retain(|entry_res| {
                    let entry = match entry_res {
                        Ok(e) => e,
                        Err(_) => return true,
                    };

                    if let Some(file_name) = entry.file_name.to_str() {
                        let lower_name = file_name.to_lowercase();
                        if ignore_folder_names_clone.contains(&lower_name) {
                            return false;
                        }
                    }

                    if entry.file_type.is_dir() {
                        let entry_path = entry.path();
                        let entry_path_str = entry_path.to_string_lossy().to_lowercase();
                        for ignored in &ignored_path_strings_clone {
                            if entry_path_str.starts_with(ignored) {
                                return false;
                            }
                        }
                    }

                    true
                });
            });

        for entry_res in walk_dir {
            let entry = match entry_res {
                Ok(e) => e,
                Err(e) => {
                    eprintln!("Warning: Error reading entry: {}", e);
                    continue;
                }
            };

            if entry.file_type.is_file() {
                let path = entry.path();
                
                // If media mode, check video extensions
                if is_media {
                    let ext = path.extension()
                        .and_then(|s| s.to_str())
                        .unwrap_or("")
                        .to_lowercase();
                    if ext != "mp4" && ext != "mkv" && ext != "avi" && ext != "mov" {
                        continue;
                    }
                }

                let size = match entry.metadata() {
                    Ok(meta) => meta.len(),
                    Err(_) => 0,
                };

                let path_str = path.to_string_lossy().to_string();
                let clean_path = if path_str.starts_with(r"\\?\") {
                    &path_str[4..]
                } else {
                    &path_str
                };

                writeln!(writer, "{} | {}", size, clean_path)?;
                file_count += 1;

                if file_count % 15000 == 0 {
                    println!("Status: Indexed {} files...", file_count);
                    let _ = std::io::stdout().flush();
                }
            }
        }
    }

    writer.flush()?;
    println!("Status: Scan complete. Total files indexed: {}", file_count);
    println!("Status: Output written to {}", output_path.display());
    Ok(())
}

