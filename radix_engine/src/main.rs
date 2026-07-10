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
}

fn load_config() -> Result<Config, Box<dyn std::error::Error>> {
    // Attempt to load config.json from current working directory first,
    // then from the executable's directory.
    let mut config_path = PathBuf::from("config.json");
    if !config_path.exists() {
        if let Ok(exe_path) = env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                config_path = exe_dir.join("config.json");
            }
        }
    }

    let file = File::open(&config_path)?;
    let reader = BufReader::new(file);
    let config: Config = serde_json::from_reader(reader)?;
    Ok(config)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Status: Initializing scanner...");
    
    let config = match load_config() {
        Ok(cfg) => cfg,
        Err(e) => {
            eprintln!("Error: Failed to load config.json: {}", e);
            std::process::exit(1);
        }
    };

    // Canonicalize scan roots and ignore paths
    let scan_paths: Vec<PathBuf> = config.scan_targets.iter()
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

    // Prepare output file next to config.json or in the current directory
    let mut output_path = PathBuf::from("hard_drive_index.txt");
    if let Ok(exe_path) = env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            if exe_dir.join("config.json").exists() {
                output_path = exe_dir.join("hard_drive_index.txt");
            }
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
                        Err(_) => return true, // Keep errors so they can be handled later
                    };

                    // 1. Check if folder/file name matches ignore list
                    if let Some(file_name) = entry.file_name.to_str() {
                        let lower_name = file_name.to_lowercase();
                        if ignore_folder_names_clone.contains(&lower_name) {
                            return false;
                        }
                    }

                    // 2. Check if the entry starts with/is equal to any ignored path
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
                    // Fail gracefully on individual entry read errors (like permission denied)
                    eprintln!("Warning: Error reading entry: {}", e);
                    continue;
                }
            };

            if entry.file_type.is_file() {
                let size = match entry.metadata() {
                    Ok(meta) => meta.len(),
                    Err(_) => 0,
                };

                let path_str = entry.path().to_string_lossy().to_string();
                let clean_path = if path_str.starts_with(r"\\?\") {
                    &path_str[4..]
                } else {
                    &path_str
                };

                writeln!(writer, "{} | {}", size, clean_path)?;
                file_count += 1;

                if file_count % 25000 == 0 {
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

