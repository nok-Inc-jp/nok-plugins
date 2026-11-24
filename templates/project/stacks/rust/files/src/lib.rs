//! __PROJECT_NAME__

/// 動作を確かめるための最初の関数。本物の機能に置き換える。
pub fn hello(name: &str) -> String {
    format!("こんにちは、{name}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hello_returns_greeting() {
        assert_eq!(hello("ノック"), "こんにちは、ノック");
    }
}
